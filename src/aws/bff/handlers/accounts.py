from src.aws.bff.auth.claims import customer_ref
from src.aws.bff.clients.core_client import CoreClient
from src.aws.bff.handlers._base import run

client = CoreClient()

def handler(event, context):
    def action(cid):
        route = event.get("routeKey", "")
        if "movements" in route:
            account_ref = (event.get("pathParameters") or {})["account_ref"]
            return client.request("GET", f"/accounts/{account_ref}/movements", correlation_id=cid, customer_ref=customer_ref(event))
        return client.request("GET", "/accounts", query={"customer_ref": customer_ref(event)}, correlation_id=cid, customer_ref=customer_ref(event))
    return run(event, action)
