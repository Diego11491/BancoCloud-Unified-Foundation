"""Host-side LOCAL FIRST smoke test. Reads demo key without printing it."""
import argparse
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8080"


def key_from_env():
    env = ROOT / ".env"
    if not env.is_file():
        raise RuntimeError("Missing .env; run python scripts/init_env.py")
    for line in env.read_text().splitlines():
        if line.startswith("DEMO_API_KEY="):
            return line.split("=",1)[1]
    raise RuntimeError("DEMO_API_KEY missing")


def request(path, key, payload=None, idempotency_key=None):
    headers = {"X-Demo-Key":key}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        headers["Idempotency-Key"] = idempotency_key
        data = json.dumps(payload).encode()
    with urlopen(Request(API+path,data=data,headers=headers),timeout=15) as response:
        return json.load(response)


def run(transfer_only=False):
    key = key_from_env()
    with urlopen(API+"/health",timeout=15) as response:
        if json.load(response).get("status") != "ok": raise RuntimeError("Core unhealthy")
    accounts = request("/accounts",key)
    if len(accounts) < 2: raise RuntimeError("Seed at least two accounts")
    source, destination = accounts[:2]
    payload = {"source_account":source["account_ref"],"destination_account":destination["account_ref"],
               "amount":"25.00","device_ref":"known-smoke-device","beneficiary_ref":"known-smoke-beneficiary"}
    def send(body):
        idempotency_key = str(uuid4())
        result = request("/transfers",key,body,idempotency_key)
        duplicate = request("/transfers",key,body,idempotency_key)
        if not duplicate.get("replay") or duplicate["transaction_id"] != result["transaction_id"]:
            raise RuntimeError("Idempotency failed")
        return result
    if transfer_only:
        result = send(payload)
        print(json.dumps({"transfer":result,"idempotency":"PASS"}))
        return result
    for _ in range(3): send(payload)
    run_marker = uuid4().hex
    high = send({
        **payload,
        "amount":"3000.00",
        "device_ref": f"new-smoke-device-{run_marker}",
        "beneficiary_ref": f"new-smoke-beneficiary-{run_marker}",
    })
    for _ in range(30):
        cases = request("/cases",key)
        matched = [c for c in cases if c["evidence"]["transaction_id"] == high["transaction_id"]]
        if matched:
            if len(matched)!=1 or matched[0]["evidence"]["correlation_id"] != high["correlation_id"]:
                raise RuntimeError("Case deduplication or correlation failed")
            print(json.dumps({"four_transfers":"PASS","idempotency":"PASS","high_case":"PASS",
                              "correlation_id":high["correlation_id"]}))
            return high
        time.sleep(1)
    raise RuntimeError("HIGH case was not created within 30 seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--transfer-only",action="store_true")
    args = parser.parse_args()
    run(args.transfer_only)
