import os
from fastapi import Header, HTTPException


def require_demo_key(x_demo_key: str | None = Header(None)) -> None:
    expected = os.environ.get("DEMO_API_KEY")
    if not expected or x_demo_key != expected:
        raise HTTPException(401, "Missing or invalid demo key")
