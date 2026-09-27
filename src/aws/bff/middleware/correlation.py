from uuid import uuid4

def correlation_id(event: dict) -> str:
    headers = {str(k).lower(): v for k, v in (event.get("headers") or {}).items()}
    return headers.get("x-correlation-id") or str(uuid4())
