import json
import os
import time
import hmac
import hashlib
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class CoreClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: float = 4.0):
        self._base_url = base_url
        self._api_key = api_key
        self.timeout = timeout

    @property
    def base_url(self) -> str:
        value = self._base_url or os.environ.get("CORE_BASE_URL")
        if not value:
            raise RuntimeError("CORE_BASE_URL is not configured")
        return value.rstrip("/")

    @property
    def api_key(self) -> str:
        value = self._api_key or os.environ.get("CORE_API_KEY")
        if not value:
            raise RuntimeError("CORE_API_KEY is not configured")
        return value

    def request(self, method: str, path: str, *, query: dict | None = None, body: dict | None = None,
                correlation_id: str | None = None, idempotency_key: str | None = None,
                customer_ref: str | None = None):
        url = self.base_url + path
        if query:
            filtered = {k: v for k, v in query.items() if v is not None}
            if filtered:
                url += "?" + urlencode(filtered)
        headers = {"Accept": "application/json", "X-Demo-Key": self.api_key}
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        if customer_ref:
            import uuid
            try:
                canon_ref = str(uuid.UUID(customer_ref))
            except ValueError:
                canon_ref = customer_ref

            ts = str(int(time.time()))
            secret = os.environ.get("BFF_IDENTITY_SECRET", "")
            canonical = f"{method}\n{path}\n{canon_ref}\n{ts}"
            signature = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
            headers["X-Customer-Ref"] = canon_ref
            headers["X-BFF-Timestamp"] = ts
            headers["X-BFF-Signature"] = signature
        data = None
        if body is not None:
            data = json.dumps(body, separators=(",", ":")).encode()
            headers["Content-Type"] = "application/json"
        req = Request(url, data=data, headers=headers, method=method)
        with urlopen(req, timeout=self.timeout) as res:
            payload = res.read()
            return json.loads(payload) if payload else None
