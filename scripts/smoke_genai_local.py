"""Host-side GenAI smoke using one governed HIGH case without printing evidence."""

from __future__ import annotations

import copy
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bancocloud.contracts import validate  # noqa: E402


CORE_API = os.environ.get("CORE_API_URL", "http://127.0.0.1:8080").rstrip("/")
GENAI_API = os.environ.get("GENAI_API_URL", "http://127.0.0.1:8082").rstrip("/")
INPUT_REFERENCE = re.compile(r"^sha256:[a-f0-9]{64}$")


def key_from_env() -> str:
    env = ROOT / ".env"
    if not env.is_file():
        raise RuntimeError("Missing .env; run python scripts/init_env.py")
    for raw_line in env.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("DEMO_API_KEY="):
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
            if key:
                return key
    raise RuntimeError("DEMO_API_KEY missing")


def request_json(url: str, key: str | None = None, payload: dict | None = None) -> dict | list:
    headers = {"Accept": "application/json"}
    if key is not None:
        headers["X-Demo-Key"] = key
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(url, data=data, headers=headers, method="POST" if data else "GET")
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def wait_for_genai(attempts: int = 10, delay_seconds: float = 2.0) -> dict:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            health = request_json(f"{GENAI_API}/health")
            if health == {"status": "ok", "critical_path": False}:
                return health
            last_error = RuntimeError("Unexpected GenAI health response")
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            last_error = exc
        time.sleep(delay_seconds)
    raise RuntimeError("GenAI did not become ready") from last_error


def expect_http_error(url: str, expected: int, key: str | None, payload: dict) -> None:
    try:
        request_json(url, key=key, payload=payload)
    except HTTPError as exc:
        if exc.code != expected:
            raise RuntimeError(f"Expected HTTP {expected}, received {exc.code}") from exc
        return
    raise RuntimeError(f"Expected HTTP {expected}, request was accepted")


def validate_summary(summary: dict, case_id: str, evidence: dict) -> None:
    validate("genai_summary", summary)
    if summary["case_id"] != case_id:
        raise RuntimeError("GenAI case reference mismatch")
    if summary["transaction_id"] != evidence["transaction_id"]:
        raise RuntimeError("GenAI transaction reference mismatch")
    if summary["correlation_id"] != evidence["correlation_id"]:
        raise RuntimeError("GenAI correlation reference mismatch")
    if not INPUT_REFERENCE.fullmatch(summary["input_reference"]):
        raise RuntimeError("GenAI input reference is not auditable")
    if not summary["human_review_required"] or summary["decision_authority"] != "HUMAN_ANALYST":
        raise RuntimeError("GenAI attempted to bypass human review")


def run() -> dict:
    key = key_from_env()
    wait_for_genai()
    core_health = request_json(f"{CORE_API}/health")
    if core_health.get("status") != "ok":
        raise RuntimeError("Core unhealthy")

    cases = request_json(f"{CORE_API}/cases?limit=1", key=key)
    if not isinstance(cases, list) or not cases:
        raise RuntimeError("No HIGH case available; run the local replay or smoke first")
    case = cases[0]
    case_id, evidence = case["case_id"], case["evidence"]
    if evidence.get("risk_level") != "HIGH":
        raise RuntimeError("GenAI smoke requires a governed HIGH case")

    endpoint = f"{GENAI_API}/explain-case"
    payload = {"case_id": case_id, "evidence": evidence}
    summary = request_json(endpoint, key=key, payload=payload)
    validate_summary(summary, case_id, evidence)

    expect_http_error(endpoint, 401, key=None, payload=payload)
    pii_evidence = copy.deepcopy(evidence)
    pii_evidence["reason_codes"] = ["CONTACT_person@example.com"]
    expect_http_error(endpoint, 400, key=key, payload={"case_id": case_id, "evidence": pii_evidence})

    result = {
        "genai_health": "PASS",
        "governed_high_case": "PASS",
        "contract_and_correlation": "PASS",
        "authentication_required": "PASS",
        "pii_rejected": "PASS",
        "human_review_required": "PASS",
        "generation_mode": summary["generation_mode"],
        "critical_path": False,
    }
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    run()
