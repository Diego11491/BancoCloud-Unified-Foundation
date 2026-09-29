"""Transport boundaries for local and explicitly enabled cloud delivery."""
import json
import os
from typing import Protocol
from urllib.request import Request, urlopen


class CloudAdapterDisabled(RuntimeError):
    pass


class CloudAdapterConfigurationError(RuntimeError):
    pass


class EventDeliveryError(RuntimeError):
    pass


class TransactionEventSink(Protocol):
    def publish(self, event: dict) -> dict: ...


class StdlibHttpTransport:
    def post(self, url: str, event: dict, key: str, timeout: int = 10) -> dict:
        request = Request(
            url,
            data=json.dumps(event).encode(),
            headers={"Content-Type": "application/json", "X-Demo-Key": key},
        )
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)


class LocalFraudHttpSink:
    def __init__(self, url: str, demo_key: str, client=None):
        self.url = url
        self.demo_key = demo_key
        self.client = client or StdlibHttpTransport()

    def publish(self, event: dict) -> dict:
        return self.client.post(self.url, event, self.demo_key, timeout=10)


class AzureEventHubsSink:
    """Passwordless Event Hubs producer with lazy Azure SDK imports."""

    def __init__(
        self,
        fully_qualified_namespace: str,
        eventhub_name: str,
        producer_factory=None,
        event_data_factory=None,
    ):
        if not fully_qualified_namespace or not eventhub_name:
            raise CloudAdapterConfigurationError(
                "Event Hubs namespace and event hub name are required"
            )
        self.fully_qualified_namespace = fully_qualified_namespace
        self.eventhub_name = eventhub_name
        self._producer_factory = producer_factory
        self._event_data_factory = event_data_factory
        self._credential = None
        self._producer = None

    def _ensure_client(self):
        if self._producer is not None:
            return
        if self._producer_factory is not None:
            self._producer = self._producer_factory(
                self.fully_qualified_namespace,
                self.eventhub_name,
            )
            return
        try:
            from azure.eventhub import EventData, EventHubProducerClient
            from azure.identity import DefaultAzureCredential
        except ImportError as exc:
            raise CloudAdapterConfigurationError(
                "Install requirements-azure.txt before enabling Event Hubs"
            ) from exc

        managed_identity_client_id = os.environ.get("AZURE_MANAGED_IDENTITY_CLIENT_ID")
        self._credential = DefaultAzureCredential(
            managed_identity_client_id=managed_identity_client_id or None,
            exclude_interactive_browser_credential=True,
        )
        self._producer = EventHubProducerClient(
            fully_qualified_namespace=self.fully_qualified_namespace,
            eventhub_name=self.eventhub_name,
            credential=self._credential,
        )
        self._event_data_factory = EventData

    def publish(self, event: dict) -> dict:
        self._ensure_client()
        event_data_factory = self._event_data_factory or (lambda value: value)
        try:
            self._producer.send_batch(
                [event_data_factory(json.dumps(event, separators=(",", ":")))]
            )
        except Exception as exc:
            raise EventDeliveryError("Event Hubs delivery failed") from exc
        return {"transport": "azure-event-hubs", "accepted": True}

    def close(self):
        if self._producer is not None and hasattr(self._producer, "close"):
            self._producer.close()
        if self._credential is not None and hasattr(self._credential, "close"):
            self._credential.close()


class AzureServiceBusCaseSink:
    def publish_high_case(self, command: dict) -> None:
        raise CloudAdapterDisabled(
            "Azure Service Bus case adapter remains disabled until the cases phase"
        )


class AwsDigitalCoreGateway:
    def send_transfer(self, request: dict) -> dict:
        raise CloudAdapterDisabled("AWS BFF/core gateway is not configured")


def transaction_event_sink(client=None):
    mode = os.environ.get("EVENT_SINK", "local-http")
    if mode == "local-http":
        return LocalFraudHttpSink(
            os.environ["FRAUD_URL"],
            os.environ["DEMO_API_KEY"],
            client,
        )
    if mode == "azure-event-hubs":
        if client is not None:
            raise CloudAdapterConfigurationError(
                "HTTP client injection is only supported by local-http"
            )
        return AzureEventHubsSink(
            os.environ.get("AZURE_EVENTHUB_FULLY_QUALIFIED_NAMESPACE", ""),
            os.environ.get("AZURE_EVENTHUB_NAME", ""),
        )
    raise CloudAdapterDisabled(f"Unsupported EVENT_SINK mode: {mode}")


def local_event_sink(client=None):
    """Backward-compatible LOCAL FIRST factory used by existing tests."""
    if os.environ.get("EVENT_SINK", "local-http") != "local-http":
        raise CloudAdapterDisabled("local_event_sink requires EVENT_SINK=local-http")
    return transaction_event_sink(client)
