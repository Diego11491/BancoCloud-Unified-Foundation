"""Event Hubs consumer for the controlled Azure vertical slice.

The first hybrid proof runs this worker from the development machine and reuses
PostgreSQL LOCAL FIRST persistence. Container Apps deployment remains blocked
until the Azure SQL adapter is ready.
"""
import json
import os

def _configured_service():
    from bancocloud.api.fraud import fraud_service
    return fraud_service


def process_received_event(partition_context, event, service=None):
    service = service or _configured_service()
    payload = json.loads(event.body_as_str(encoding="UTF-8"))
    result = service.ingest(payload)
    partition_context.update_checkpoint(event)
    print(
        json.dumps(
            {
                "event_id": payload.get("event_id"),
                "transaction_id": payload.get("transaction_id"),
                "risk_level": result["score"]["risk_level"],
                "replay": result["replay"],
                "checkpoint": "updated",
            },
            separators=(",", ":"),
        ),
        flush=True,
    )
    return result


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required Azure setting: {name}")
    return value


def run():
    try:
        from azure.eventhub import EventHubConsumerClient
        from azure.eventhub.extensions.checkpointstoreblob import BlobCheckpointStore
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise RuntimeError(
            "Install requirements-azure.txt before starting the Azure worker"
        ) from exc

    namespace = _required("AZURE_EVENTHUB_FULLY_QUALIFIED_NAMESPACE")
    eventhub_name = _required("AZURE_EVENTHUB_NAME")
    blob_account_url = _required("AZURE_BLOB_ACCOUNT_URL")
    checkpoint_container = os.environ.get(
        "AZURE_BLOB_CHECKPOINT_CONTAINER", "eventhub-checkpoints"
    )
    consumer_group = os.environ.get("AZURE_EVENTHUB_CONSUMER_GROUP", "fraud-engine")
    managed_identity_client_id = os.environ.get("AZURE_MANAGED_IDENTITY_CLIENT_ID")

    credential = DefaultAzureCredential(
        managed_identity_client_id=managed_identity_client_id or None,
        exclude_interactive_browser_credential=True,
    )
    checkpoint_store = BlobCheckpointStore(
        blob_account_url=blob_account_url,
        container_name=checkpoint_container,
        credential=credential,
    )
    consumer = EventHubConsumerClient(
        fully_qualified_namespace=namespace,
        eventhub_name=eventhub_name,
        consumer_group=consumer_group,
        credential=credential,
        checkpoint_store=checkpoint_store,
    )
    try:
        with consumer:
            consumer.receive(
                on_event=process_received_event,
                starting_position="-1",
            )
    finally:
        credential.close()


if __name__ == "__main__":
    run()
