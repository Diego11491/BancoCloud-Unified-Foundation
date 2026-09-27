class Unauthorized(ValueError): pass


def claims(event: dict) -> dict:
    auth = (((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt") or {}).get("claims") or {}
    if not auth.get("sub"):
        raise Unauthorized("JWT subject missing")
    return auth


def customer_ref(event: dict) -> str:
    c = claims(event)
    value = c.get("custom:customer_ref") or c.get("customer_ref")
    if not value:
        raise Unauthorized("customer_ref claim missing")
    return value
