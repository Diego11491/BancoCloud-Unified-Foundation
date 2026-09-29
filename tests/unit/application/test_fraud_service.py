import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from bancocloud.application.fraud_service import FraudContractError, FraudService
from bancocloud.repositories.fraud import FraudEvaluation


class FakeEvaluationStore:
    def __init__(self, history=(), replay=False):
        self.history = list(history)
        self.replay = replay

    def evaluate_once(self, event, evaluator):
        return FraudEvaluation(score=evaluator(self.history), replay=self.replay)


class FakeHighCaseSink:
    def __init__(self):
        self.commands = []

    def publish_high_case(self, command):
        self.commands.append(command)


def event_at(when, *, amount=25.0, device="known-device", beneficiary="known-beneficiary"):
    return {
        "schema_version": "1.0",
        "event_id": str(uuid4()),
        "event_type": "TransactionPosted",
        "event_time": when.isoformat(),
        "transaction_id": str(uuid4()),
        "customer_ref": str(uuid4()),
        "account_ref": str(uuid4()),
        "transaction_type": "TRANSFER",
        "amount": amount,
        "currency": "PEN",
        "channel": "API",
        "authentication_method": "SESSION",
        "transaction_status": "POSTED",
        "device_ref": device,
        "beneficiary_ref": beneficiary,
        "location": {"country": "PE", "region": "Lima"},
        "correlation_id": str(uuid4()),
        "source_system": "unit-test",
    }


class FraudServiceTests(unittest.TestCase):
    def test_low_does_not_publish_case(self):
        sink = FakeHighCaseSink()
        result = FraudService(FakeEvaluationStore(), sink).ingest(
            event_at(datetime.now(timezone.utc))
        )
        self.assertEqual(result["score"]["risk_level"], "LOW")
        self.assertFalse(result["replay"])
        self.assertEqual(sink.commands, [])

    def test_high_publishes_only_contractual_case_command(self):
        now = datetime.now(timezone.utc)
        current = event_at(now, amount=5000.0, device="new-device", beneficiary="new-beneficiary")
        history = []
        for seconds in (40, 50, 60, 70):
            prior = event_at(now - timedelta(seconds=seconds))
            prior["customer_ref"] = current["customer_ref"]
            history.append(prior)
        sink = FakeHighCaseSink()

        result = FraudService(FakeEvaluationStore(history), sink).ingest(current)

        self.assertEqual(result["score"]["risk_level"], "HIGH")
        self.assertEqual(len(sink.commands), 1)
        self.assertEqual(sink.commands[0]["transaction_id"], current["transaction_id"])
        self.assertEqual(sink.commands[0]["correlation_id"], current["correlation_id"])

    def test_high_replay_republishes_for_idempotent_recovery(self):
        now = datetime.now(timezone.utc)
        current = event_at(now, amount=5000.0, device="new-device", beneficiary="new-beneficiary")
        history = []
        for seconds in (40, 50, 60, 70):
            prior = event_at(now - timedelta(seconds=seconds))
            prior["customer_ref"] = current["customer_ref"]
            history.append(prior)
        sink = FakeHighCaseSink()

        result = FraudService(FakeEvaluationStore(history, replay=True), sink).ingest(current)

        self.assertTrue(result["replay"])
        self.assertEqual(len(sink.commands), 1)

    def test_invalid_event_is_rejected_before_storage(self):
        sink = FakeHighCaseSink()
        with self.assertRaises(FraudContractError):
            FraudService(FakeEvaluationStore(), sink).ingest({"invalid": True})
        self.assertEqual(sink.commands, [])


if __name__ == "__main__":
    unittest.main()
