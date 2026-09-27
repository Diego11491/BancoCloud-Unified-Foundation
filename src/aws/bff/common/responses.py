import json

def response(status_code: int, body, *, headers: dict | None = None) -> dict:
    base = {"Content-Type": "application/json"}
    if headers: base.update(headers)
    return {"statusCode": status_code, "headers": base, "body": json.dumps(body, separators=(",", ":"), default=str)}
