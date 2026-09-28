"""CORS policy for the LOCAL FIRST Core API."""

import os
from urllib.parse import urlsplit


DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:8081",
    "http://127.0.0.1:8081",
)


def parse_allowed_origins(raw: str) -> list[str]:
    """Parse and validate a comma-separated allowlist of HTTP origins."""
    origins: list[str] = []
    for value in raw.split(","):
        origin = value.strip().rstrip("/")
        if not origin:
            continue
        if origin == "*":
            raise ValueError("CORS wildcard origins are not allowed")

        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ValueError(f"Invalid CORS origin: {origin}")

        if origin not in origins:
            origins.append(origin)
    return origins


def allowed_origins() -> list[str]:
    configured = os.getenv("CORS_ALLOWED_ORIGINS")
    if configured is None:
        return list(DEFAULT_ALLOWED_ORIGINS)
    return parse_allowed_origins(configured)
