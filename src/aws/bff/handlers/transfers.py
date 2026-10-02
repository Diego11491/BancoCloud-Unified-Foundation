from src.aws.bff.auth.claims import customer_ref
from src.aws.bff.clients.core_client import CoreClient
from src.aws.bff.common.responses import response
from src.aws.bff.handlers._base import body, run
from src.aws.bff.middleware.correlation import correlation_id

client = CoreClient()


def handler(event, context):
    headers = {str(k).lower(): v for k, v in (event.get("headers") or {}).items()}
    key = headers.get("idempotency-key")
    if not key:
        cid = correlation_id(event)
        return response(400, {"error": "missing_idempotency_key", "correlation_id": cid}, headers={"X-Correlation-Id": cid})

    def action(cid):
        return client.request("POST", "/transfers", body=body(event), correlation_id=cid, idempotency_key=key, customer_ref=customer_ref(event))
    return run(event, action)
