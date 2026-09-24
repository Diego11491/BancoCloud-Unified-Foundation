"""Transport boundaries. Cloud adapters intentionally have no client or credentials."""
import os
import json
from typing import Protocol
from urllib.request import Request, urlopen


class CloudAdapterDisabled(RuntimeError):
    pass


class TransactionEventSink(Protocol):
    def publish(self, event: dict) -> dict: ...


class StdlibHttpTransport:
    def post(self, url: str, event: dict, key: str, timeout: int = 10) -> dict:
        request = Request(url, data=json.dumps(event).encode(),headers={"Content-Type":"application/json","X-Demo-Key":key})
        with urlopen(request,timeout=timeout) as response:
            return json.load(response)


class LocalFraudHttpSink:
    def __init__(self, url: str, demo_key: str, client=None):
        self.url, self.demo_key, self.client = url, demo_key, client or StdlibHttpTransport()

    def publish(self, event: dict) -> dict:
        return self.client.post(self.url,event,self.demo_key,timeout=10)


class AzureEventHubsSink:
    def publish(self, event: dict) -> None:
        raise CloudAdapterDisabled("Azure Event Hubs adapter is a scaffold; no connection is configured")


class AzureServiceBusCaseSink:
    def publish_high_case(self, command: dict) -> None:
        raise CloudAdapterDisabled("Azure Service Bus adapter is a scaffold; no connection is configured")


class AwsDigitalCoreGateway:
    def send_transfer(self, request: dict) -> dict:
        raise CloudAdapterDisabled("AWS BFF/core gateway is a scaffold; no connection is configured")


def local_event_sink(client=None):
    if os.environ.get("EVENT_SINK", "local-http") != "local-http":
        raise CloudAdapterDisabled("Only local-http is enabled in LOCAL FIRST")
    return LocalFraudHttpSink(os.environ["FRAUD_URL"],os.environ["DEMO_API_KEY"],client)
