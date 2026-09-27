import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from bancocloud.adapters import AzureEventHubsSink, AzureServiceBusCaseSink, AwsDigitalCoreGateway, CloudAdapterDisabled
from bancocloud.replay import replay
from bancocloud import gates

ROOT = Path(__file__).resolve().parents[1]


class FakeTransport:
    def __init__(self, fail_once=False):
        self.seen = set()
        self.fail_once = fail_once
        self.calls = 0

    def post(self, url, event, key, timeout):
        self.calls += 1
        if self.fail_once:
            self.fail_once = False
            raise HTTPError(url,503,"demo failure",{},None)
        duplicate = event["event_id"] in self.seen
        self.seen.add(event["event_id"])
        return {"score":{"correlation_id":event["correlation_id"]},"replay":duplicate}


class BoundaryTests(unittest.TestCase):
    def test_gate_checks_counts_and_blockers(self):
        values = [10000,10000,93,93,0,0,0,0,0,0,0,0]
        class FakeDB:
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def execute(self,query):
                class Row:
                    def __init__(self,value): self.value=value
                    def fetchone(self): return (self.value,)
                return Row(values.pop(0))
        with patch.object(gates,"connect",FakeDB):
            report = gates.run(10000)
        self.assertTrue(report["pass"])
        values = [10000,10000,93,93,1,0,0,0,0,0,0,0]
        with patch.object(gates,"connect",FakeDB):
            report = gates.run(10000)
        self.assertFalse(report["pass"])
        self.assertFalse(report["checks"]["no_medium_cases"])

    def test_replay_resumes_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as tmp, (ROOT/"data/synthetic/transaction_events.jsonl").open() as source:
            path = Path(tmp)/"fixture.jsonl"
            path.write_text(next(source)+next(source))
            client = FakeTransport(fail_once=True)
            with patch.dict(os.environ,{"EVENT_SINK":"local-http","FRAUD_URL":"http://fraud:8000/ingest","DEMO_API_KEY":"demo-test"}):
                first = replay(path,2,client=client,pause=lambda _:None,progress=0)
                second = replay(path,2,client=client,pause=lambda _:None,progress=0)
            self.assertEqual((first["accepted"],first["replayed"]),(2,0))
            self.assertEqual((second["accepted"],second["replayed"]),(0,2))
            self.assertEqual(client.calls,5)

    def test_cloud_boundaries_are_disabled(self):
        with self.assertRaises(CloudAdapterDisabled): AzureEventHubsSink().publish({})
        with self.assertRaises(CloudAdapterDisabled): AzureServiceBusCaseSink().publish_high_case({})
        with self.assertRaises(CloudAdapterDisabled): AwsDigitalCoreGateway().send_transfer({})

    def test_compose_runs_idempotent_product_migration_before_modular_core(self):
        compose = (ROOT / "docker-compose.yml").read_text()
        dockerfile = (ROOT / "Dockerfile").read_text()
        migration = (ROOT / "infra/local/migrations/002_cards_loans.sql").read_text()
        self.assertIn("002_cards_loans.sql:/docker-entrypoint-initdb.d/002_cards_loans.sql:ro", compose)
        self.assertIn("migrate:", compose)
        self.assertIn("service_completed_successfully", compose)
        self.assertIn("bancocloud.api.core:app", dockerfile)
        self.assertIn("CREATE TABLE IF NOT EXISTS cards", migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS loans", migration)


if __name__ == "__main__": unittest.main()
