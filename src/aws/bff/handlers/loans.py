from src.aws.bff.auth.claims import customer_ref
from src.aws.bff.clients.core_client import CoreClient
from src.aws.bff.handlers._base import body, run
client = CoreClient()
def handler(event, context):
    def action(cid):
        if event.get("requestContext", {}).get("http", {}).get("method") == "POST":
            return client.request("POST", "/loans/apply", body=body(event), correlation_id=cid, customer_ref=customer_ref(event))
        return client.request("GET", "/loans", query={"customer_ref": customer_ref(event)}, correlation_id=cid, customer_ref=customer_ref(event))
    return run(event, action)
