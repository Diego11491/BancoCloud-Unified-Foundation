import json
from src.aws.bff.auth.claims import Unauthorized
from src.aws.bff.common.responses import response
from src.aws.bff.middleware.errors import handle_error
from src.aws.bff.middleware.correlation import correlation_id


def body(event: dict) -> dict:
    raw = event.get("body")
    if not raw: return {}
    if isinstance(raw, dict): return raw
    return json.loads(raw)


def run(event: dict, action):
    cid = correlation_id(event)
    try:
        result = action(cid)
        return response(200, result, headers={"X-Correlation-Id": cid})
    except Unauthorized as exc:
        return response(401, {"error": "unauthorized", "detail": str(exc), "correlation_id": cid})
    except Exception as exc:
        return handle_error(exc, cid)
