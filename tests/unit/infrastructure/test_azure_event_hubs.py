import json
import unittest

from bancocloud.adapters import AzureEventHubsSink, EventDeliveryError
from bancocloud.azure_event_worker import process_received_event


class FakeProducer:
    def __init__(self, fail=False):
        self.fail = fail
        self.batches = []
        self.closed = False

    def send_batch(self, batch):
        if self.fail:
            raise RuntimeError("broker unavailable")
        self.batches.append(batch)

    def close(self):
        self.closed = True


class FakeEvent:
    def __init__(self, payload):
        self.payload = payload

    def body_as_str(self, encoding="UTF-8"):
        return json.dumps(self.payload)


class FakePartition:
    def __init__(self):
        self.checkpoints = []

    def update_checkpoint(self, event):
        self.checkpoints.append(event)


class FakeFraudService:
    def __init__(self, fail=False):
        self.fail = fail
        self.events = []

    def ingest(self, event):
        if self.fail:
            raise RuntimeError("persistence failed")
        self.events.append(event)
        return {"score": {"risk_level": "LOW"}, "replay": False}


class AzureEventHubsAdapterTests(unittest.TestCase):
    def test_sender_serializes_one_event_without_credentials_in_payload(self):
        producer = FakeProducer()
        sink = AzureEventHubsSink(
            "namespace.servicebus.windows.net",
            "transaction-posted-v1",
            producer_factory=lambda namespace, name: producer,
            event_data_factory=json.loads,
        )

        result = sink.publish({"event_id": "event-1", "amount": 25})
        sink.close()

        self.assertEqual(producer.batches, [[{"event_id": "event-1", "amount": 25}]])
        self.assertEqual(result["transport"], "azure-event-hubs")
        self.assertTrue(producer.closed)

    def test_sender_wraps_transport_failure(self):
        sink = AzureEventHubsSink(
            "namespace.servicebus.windows.net",
            "transaction-posted-v1",
            producer_factory=lambda namespace, name: FakeProducer(fail=True),
        )

        with self.assertRaises(EventDeliveryError):
            sink.publish({"event_id": "event-1"})

    def test_worker_checkpoints_only_after_successful_processing(self):
        event = FakeEvent({"event_id": "event-1", "transaction_id": "tx-1"})
        partition = FakePartition()
        service = FakeFraudService()

        process_received_event(partition, event, service)

        self.assertEqual(service.events[0]["event_id"], "event-1")
        self.assertEqual(partition.checkpoints, [event])

    def test_worker_does_not_checkpoint_failed_processing(self):
        event = FakeEvent({"event_id": "event-1", "transaction_id": "tx-1"})
        partition = FakePartition()

        with self.assertRaisesRegex(RuntimeError, "persistence failed"):
            process_received_event(partition, event, FakeFraudService(fail=True))

        self.assertEqual(partition.checkpoints, [])


if __name__ == "__main__":
    unittest.main()
