from src.aws.bff.clients.core_client import CoreClient
from src.aws.bff.handlers._base import body, run
client = CoreClient()
def handler(event, context):
    return run(event, lambda cid: client.request("POST", "/onboarding", body=body(event), correlation_id=cid))
