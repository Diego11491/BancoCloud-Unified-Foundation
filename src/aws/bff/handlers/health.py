from src.aws.bff.clients.core_client import CoreClient
from src.aws.bff.handlers._base import run
client = CoreClient()
def handler(event, context):
    return run(event, lambda cid: {"status": "ok", "core": client.request("GET", "/health", correlation_id=cid)})
