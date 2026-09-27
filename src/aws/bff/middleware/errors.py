from urllib.error import HTTPError, URLError
from src.aws.bff.common.responses import response


def handle_error(exc: Exception, correlation_id: str) -> dict:
    if isinstance(exc, HTTPError):
        try: detail = exc.read().decode("utf-8")
        except Exception: detail = "Core request failed"
        return response(exc.code, {"error": "core_error", "detail": detail, "correlation_id": correlation_id})
    if isinstance(exc, URLError):
        return response(502, {"error": "core_unavailable", "correlation_id": correlation_id})
    return response(500, {"error": "internal_error", "correlation_id": correlation_id})
