import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from bancocloud.azure_medallion import _upload_immutable, land_bronze, promote


class Exists(Exception):
    pass


class MemoryContainer:
    def __init__(self):
        self.blobs = {}
        self.fail = False

    def upload_blob(self, name, content, overwrite=False):
        if self.fail:
            raise RuntimeError("storage unavailable")
        if name in self.blobs and not overwrite:
            raise Exists(name)
        self.blobs[name] = content

    def list_blobs(self, name_starts_with):
        return [SimpleNamespace(name=name) for name in self.blobs if name.startswith(name_starts_with)]

    def download_blob(self, name):
        return SimpleNamespace(readall=lambda: self.blobs[name])


class MemoryStorage:
    def __init__(self):
        self.containers = {key: MemoryContainer() for key in ("bronze", "silver", "gold", "quarantine")}

    def get_container_client(self, name):
        return self.containers[name]


class MedallionTests(unittest.TestCase):
    def setUp(self):
        self.storage = MemoryStorage()
        self.partition = SimpleNamespace(checkpoints=[])
        self.partition.update_checkpoint = self.partition.checkpoints.append

    def event(self, suffix="1", amount=25):
        payload = {
            "schema_version": "1.0", "event_id": str(UUID(int=int(suffix))),
            "event_type": "TransactionPosted", "event_time": "2026-10-02T23:00:00Z",
            "transaction_id": str(UUID(int=int(suffix) + 100)),
            "customer_ref": "customer-synthetic-001", "account_ref": "account-synthetic-001",
            "transaction_type": "TRANSFER", "amount": amount, "currency": "PEN",
            "channel": "MOBILE", "authentication_method": "PASSWORD_MFA",
            "transaction_status": "POSTED", "correlation_id": str(UUID(int=int(suffix) + 200)),
        }
        return SimpleNamespace(body_as_str=lambda encoding: json.dumps(payload))

    def test_bronze_replay_and_checkpoint_after_durable_write(self):
        container = self.storage.get_container_client("bronze")
        event = self.event()
        first = land_bronze(self.partition, event, container, Exists)
        second = land_bronze(self.partition, event, container, Exists)
        self.assertFalse(first["replay"])
        self.assertTrue(second["replay"])
        self.assertEqual(len(container.blobs), 1)
        self.assertEqual(self.partition.checkpoints, [event, event])

        container.fail = True
        with self.assertRaisesRegex(RuntimeError, "storage unavailable"):
            land_bronze(self.partition, self.event("2"), container, Exists)
        self.assertEqual(len(self.partition.checkpoints), 2)

    def test_promotes_snapshot_reconciles_and_is_idempotent(self):
        for event in (self.event("1"), self.event("2", 50)):
            land_bronze(self.partition, event, self.storage.get_container_client("bronze"), Exists)
        # An invalid JSON body stays in Bronze but never reaches Silver or Gold.
        broken = SimpleNamespace(body_as_str=lambda encoding: "{invalid")
        land_bronze(self.partition, broken, self.storage.get_container_client("bronze"), Exists)

        result = promote(self.storage, Exists)
        self.assertEqual((result["bronze"], result["silver"], result["duplicate"], result["quarantine"]), (3, 2, 0, 1))
        prefix = "runs/" + result["run_id"]
        gold = self.storage.get_container_client("gold").blobs
        row = json.loads(gold[f"{prefix}/transactions_by_day_channel.jsonl"])
        self.assertEqual(row["transaction_count"], 2)
        self.assertEqual(row["amount_pen"], 75)
        self.assertIn(f"{prefix}/manifest.json", gold)
        self.assertEqual(promote(self.storage, Exists), result)

    def test_replay_accepts_legacy_windows_line_endings_without_overwriting(self):
        for event in (self.event("1"), self.event("2", 50)):
            land_bronze(self.partition, event, self.storage.get_container_client("bronze"), Exists)
        result = promote(self.storage, Exists)
        for zone in ("silver", "gold", "quarantine"):
            blobs = self.storage.get_container_client(zone).blobs
            for name, payload in list(blobs.items()):
                blobs[name] = payload.replace(b"\n", b"\r\n")
        previous = {
            zone: dict(self.storage.get_container_client(zone).blobs)
            for zone in ("silver", "gold", "quarantine")
        }

        self.assertEqual(promote(self.storage, Exists), result)
        for zone, blobs in previous.items():
            self.assertEqual(self.storage.get_container_client(zone).blobs, blobs)

    def test_immutable_upload_rejects_content_change_and_canonicalizes_new_lines(self):
        container = self.storage.get_container_client("silver")
        name = "runs/demo/events.jsonl"
        _upload_immutable(container, name, b'{"amount":1}\r\n', Exists)
        self.assertEqual(container.blobs[name], b'{"amount":1}\n')
        with self.assertRaisesRegex(RuntimeError, "Conflicting immutable"):
            _upload_immutable(container, name, b'{"amount":2}\r\n', Exists)

    def test_conflicting_event_identity_never_publishes_gold(self):
        bronze = self.storage.get_container_client("bronze")
        for event in (self.event("1"), self.event("1", 99)):
            land_bronze(self.partition, event, bronze, Exists)
        with self.assertRaisesRegex(RuntimeError, "Conflicting Bronze bodies"):
            promote(self.storage, Exists)
        self.assertEqual(self.storage.get_container_client("gold").blobs, {})

    def test_messaging_declares_independent_consumer_and_checkpoint(self):
        bicep = (Path(__file__).resolve().parents[3] / "infra/azure/bicep/messaging-lite.bicep").read_text()
        self.assertIn("name: 'lake-writer'", bicep)
        self.assertIn("name: 'bronze-checkpoints'", bicep)
        self.assertIn("scope: bronzeCheckpoints", bicep)
        self.assertIn("scope: bronze", bicep)


if __name__ == "__main__":
    unittest.main()
