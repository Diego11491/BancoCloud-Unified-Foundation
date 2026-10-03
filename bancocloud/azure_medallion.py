"""Small, replay-safe Azure cold path for synthetic Event Hubs events.

Bronze is written independently of the fraud consumer. Promotion reuses the
LOCAL FIRST contract validation and reconciliation from ``bancocloud.cold``.
"""

import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from .cold import project


def _required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required Azure setting: {name}")
    return value


def land_bronze(partition_context, event, bronze_container, resource_exists):
    """Acknowledge an event only after its immutable raw body exists in ADLS."""
    raw = event.body_as_str(encoding="UTF-8").encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    name = f"events/{digest}.json"
    try:
        bronze_container.upload_blob(name, raw, overwrite=False)
        replay = False
    except resource_exists:
        # The path is the digest of the body: an identical retry is safe.
        replay = True
    partition_context.update_checkpoint(event)
    result = {"blob": name, "replay": replay, "checkpoint": "updated"}
    print(json.dumps(result, separators=(",", ":")), flush=True)
    return result


def _upload_immutable(container, name, payload, resource_exists):
    # JSON artifacts can be produced on Windows or Linux. Keep the first blob
    # intact, but compare logical line endings on a retry across platforms.
    if name.endswith((".json", ".jsonl")):
        payload = payload.replace(b"\r\n", b"\n")
    try:
        container.upload_blob(name, payload, overwrite=False)
    except resource_exists:
        # A previous promotion may have stopped before publishing its manifest.
        existing = container.download_blob(name).readall()
        if name.endswith((".json", ".jsonl")):
            existing = existing.replace(b"\r\n", b"\n")
        if existing != payload:
            raise RuntimeError(f"Conflicting immutable Medallion artifact: {name}")


def promote(blob_service, resource_exists):
    """Publish one reproducible Silver/Gold run from a bounded Bronze listing."""
    bronze = blob_service.get_container_client("bronze")
    silver = blob_service.get_container_client("silver")
    gold = blob_service.get_container_client("gold")
    quarantine = blob_service.get_container_client("quarantine")
    names = sorted(
        blob.name for blob in bronze.list_blobs(name_starts_with="events/")
        if blob.name.endswith(".json")
    )
    if not names:
        raise RuntimeError("Bronze contains no Event Hubs events; no Gold run published")
    run_id = hashlib.sha256("\n".join(names).encode("utf-8")).hexdigest()[:20]
    prefix = f"runs/{run_id}"

    with TemporaryDirectory(prefix="bancocloud-medallion-") as directory:
        root = Path(directory)
        events = root / "events.jsonl"
        event_digests = {}
        with events.open("w", encoding="utf-8") as output:
            for name in names:
                raw = bronze.download_blob(name).readall()
                if hashlib.sha256(raw).hexdigest() != Path(name).stem:
                    raise RuntimeError(f"Bronze content changed after landing: {name}")
                try:
                    document = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    document = None  # The unchanged raw body stays in Bronze.
                if isinstance(document, dict) and isinstance(document.get("event_id"), str):
                    event_id = document["event_id"]
                    previous = event_digests.setdefault(event_id, Path(name).stem)
                    if previous != Path(name).stem:
                        raise RuntimeError("Conflicting Bronze bodies share an event_id; Gold was not published")
                output.write(json.dumps(document, separators=(",", ":")) + "\n")

        counts = project(events, root / "lake")
        artifacts = (
            (silver, "events.jsonl", root / "lake/silver/events.jsonl"),
            (gold, "transactions_by_day_channel.jsonl", root / "lake/gold/transactions_by_day_channel.jsonl"),
            (quarantine, "rejected.jsonl", root / "lake/quarantine/rejected.jsonl"),
            (gold, "reconciliation.json", root / "lake/reconciliation.json"),
        )
        for container, filename, path in artifacts:
            _upload_immutable(container, f"{prefix}/{filename}", path.read_bytes(), resource_exists)

        manifest = json.dumps(
            {"run_id": run_id, "source": "azure-event-hubs", "counts": counts},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        # The manifest is the last write; its presence indicates a complete run.
        _upload_immutable(gold, f"{prefix}/manifest.json", manifest, resource_exists)
    return {"run_id": run_id, **counts}


def run_bronze():
    from azure.core.exceptions import ResourceExistsError
    from azure.eventhub import EventHubConsumerClient
    from azure.eventhub.extensions.checkpointstoreblob import BlobCheckpointStore
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    namespace = _required("AZURE_EVENTHUB_FULLY_QUALIFIED_NAMESPACE")
    hub = _required("AZURE_EVENTHUB_NAME")
    account_url = _required("AZURE_BLOB_ACCOUNT_URL")
    client_id = os.environ.get("AZURE_MANAGED_IDENTITY_CLIENT_ID") or None
    credential = DefaultAzureCredential(
        managed_identity_client_id=client_id,
        exclude_interactive_browser_credential=True,
    )
    try:
        blob_service = BlobServiceClient(account_url=account_url, credential=credential)
        bronze = blob_service.get_container_client("bronze")
        checkpoint_store = BlobCheckpointStore(
            blob_account_url=account_url,
            container_name="bronze-checkpoints",
            credential=credential,
        )
        consumer = EventHubConsumerClient(
            fully_qualified_namespace=namespace,
            eventhub_name=hub,
            consumer_group="lake-writer",
            credential=credential,
            checkpoint_store=checkpoint_store,
        )
        with consumer:
            consumer.receive(
                on_event=lambda context, event: land_bronze(
                    context, event, bronze, ResourceExistsError
                ) if event is not None else None,
                starting_position="-1",
            )
    finally:
        if "blob_service" in locals():
            blob_service.close()
        credential.close()


def run_promotion():
    from azure.core.exceptions import ResourceExistsError
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    account_url = _required("AZURE_BLOB_ACCOUNT_URL")
    credential = DefaultAzureCredential(
        managed_identity_client_id=os.environ.get("AZURE_MANAGED_IDENTITY_CLIENT_ID") or None,
        exclude_interactive_browser_credential=True,
    )
    try:
        service = BlobServiceClient(account_url=account_url, credential=credential)
        print(json.dumps(promote(service, ResourceExistsError), sort_keys=True))
    finally:
        if "service" in locals():
            service.close()
        credential.close()
