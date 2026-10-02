import hmac
import hashlib
import time
import os
from uuid import UUID
from fastapi import Header, HTTPException, Request


def require_demo_key(x_demo_key: str | None = Header(None)) -> None:
    expected = os.environ.get("DEMO_API_KEY")
    if not expected or x_demo_key != expected:
        raise HTTPException(401, "Missing or invalid demo key")

def require_identity(
    request: Request,
    x_customer_ref: UUID | None = Header(None),
    x_bff_timestamp: str | None = Header(None),
    x_bff_signature: str | None = Header(None)
) -> UUID:
    if not x_customer_ref or not x_bff_timestamp or not x_bff_signature:
        raise HTTPException(401, "Missing or invalid authenticated identity")

    secret = os.environ.get("BFF_IDENTITY_SECRET")
    if not secret:
        raise HTTPException(401, "Missing or invalid authenticated identity")

    try:
        ts = int(x_bff_timestamp)
    except ValueError:
        raise HTTPException(401, "Missing or invalid authenticated identity")

    skew = int(os.environ.get("BFF_IDENTITY_MAX_SKEW_SECONDS", "300"))
    if abs(time.time() - ts) > skew:
        raise HTTPException(401, "Missing or invalid authenticated identity")

    method = request.method
    path = request.url.path
    canonical = f"{method}\n{path}\n{str(x_customer_ref)}\n{x_bff_timestamp}"

    expected_mac = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_mac, x_bff_signature):
        raise HTTPException(401, "Missing or invalid authenticated identity")

    return x_customer_ref
