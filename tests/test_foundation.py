import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from bancocloud.contracts import validate
from bancocloud.engine import high_case_command, load_policy, score_event
from bancocloud.cold import project

ROOT = Path(__file__).resolve().parents[1]


class FoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / "data/synthetic/transaction_events.jsonl").open() as source:
            cls.event = json.loads(next(source))

    def test_contract_and_leakage(self):
        event = self.event
        validate("transaction", event)
        for forbidden in ("fraud_label","fraud_scenario","score_riesgo","alerta_sistema","fraude_confirmado"):
            self.assertNotIn(forbidden,event)
            with self.assertRaises(Exception): validate("transaction", {**event,forbidden:1})
        with self.assertRaises(Exception): validate("transaction", {**event,"amount":-1})

    def test_policy_and_case_boundary(self):
        low = score_event(self.event)
        if self.event["amount"] < load_policy()["large_amount_pen"]:
            self.assertEqual(low["risk_level"],"LOW")
        self.assertIsNone(high_case_command({**low,"risk_level":"MEDIUM"}))
        now = datetime.now(timezone.utc)
        history = []
        for i in range(4):
            h = {**self.event,"event_time":(now-timedelta(seconds=50+i)).isoformat(),
                 "event_id":str(uuid4()),"device_ref":"known-device","beneficiary_ref":"known-beneficiary"}
            history.append(h)
        suspicious = {**self.event,"event_id":str(uuid4()),"transaction_id":str(uuid4()),
                      "event_time":now.isoformat(),"amount":5000,"device_ref":"new-device","beneficiary_ref":"new-beneficiary"}
        score = score_event(suspicious,history)
        self.assertEqual(score["risk_level"],"HIGH")
        self.assertEqual(score["correlation_id"], suspicious["correlation_id"])
        command = high_case_command(score)
        self.assertEqual(command["command_id"],high_case_command(score)["command_id"])
        self.assertEqual(command["correlation_id"],suspicious["correlation_id"])

    def test_generator_reproducible(self):
        from data.generator.build import generate
        with (ROOT / "data/synthetic/customer_seed.jsonl").open() as source:
            profiles = [json.loads(next(source))]
        first = list(generate(profiles, count=4, seed=13))
        second = list(generate(profiles, count=4, seed=13))
        self.assertEqual(first, second)
        self.assertEqual(set(first[0][0]).intersection(first[0][1]), {"transaction_id"})

    def test_analyst_decision_contract(self):
        payload = {"schema_version":"1.0","case_id":str(uuid4()),"transaction_id":self.event["transaction_id"],
                   "decision":"INCONCLUSIVE","decided_at":datetime.now(timezone.utc).isoformat(),
                   "analyst_ref":"synthetic-analyst-01","correlation_id":self.event["correlation_id"]}
        validate("decision",payload)
        with self.assertRaises(Exception): validate("decision",{**payload,"decision":"BLOCK_ACCOUNT"})

    def test_cold_reconciliation(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "events.jsonl"
            source.write_text(json.dumps(self.event)+"\n"+json.dumps(self.event)+"\n"+'{"invalid":true}\n')
            result = project(source,Path(temp)/"lake")
            self.assertEqual(result,{"bronze":3,"silver":1,"quarantine":1,"duplicate":1})

    def test_quarantine_is_declared_as_a_private_lake_side_zone(self):
        messaging = (ROOT / "infra/azure/bicep/messaging-lite.bicep").read_text()
        main = (ROOT / "infra/azure/bicep/main-lite.bicep").read_text()
        self.assertIn("resource quarantine", messaging)
        self.assertIn("name: 'quarantine'", messaging)
        self.assertIn("properties: { publicAccess: 'None' }", messaging)
        self.assertIn("delete-expired-quarantine", messaging)
        self.assertIn("prefixMatch", messaging)
        self.assertIn("'quarantine/'", messaging)
        self.assertIn("output quarantineContainerName", messaging)
        self.assertIn("messaging.outputs.quarantineContainerName", main)

    def test_event_hubs_checkpoint_and_least_privilege_rbac_are_declared(self):
        messaging = (ROOT / "infra/azure/bicep/messaging-lite.bicep").read_text()
        main = (ROOT / "infra/azure/bicep/main-lite.bicep").read_text()
        self.assertIn("name: 'fraud-engine'", messaging)
        self.assertIn("name: 'eventhub-checkpoints'", messaging)
        self.assertIn("a638d3c7-ab3a-418d-83e6-5f17a39d4fde", messaging)
        self.assertIn("2b629674-e913-4c01-ae53-ef4638d8f975", messaging)
        self.assertIn("ba92f5b4-2d11-453d-a403-e96b0029c9fe", messaging)
        self.assertIn("workloadIdentityPrincipalId: foundation.outputs.workloadIdentityPrincipalId", main)
        self.assertNotIn("listKeys(", messaging)
        self.assertNotIn("RootManageSharedAccessKey", messaging)

    def test_ci_validates_without_cloud_deployment(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn("python -m unittest", workflow)
        self.assertIn("az bicep lint", workflow)
        self.assertIn("az bicep build", workflow)
        self.assertNotIn("azure/login", workflow)
        self.assertNotIn("az deployment", workflow)


if __name__ == "__main__": unittest.main()
