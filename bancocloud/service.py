"""On-premise simulator and LOCAL FIRST fraud consumer; no live money or real identifiers."""
import json
import os
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .contracts import validate
from .engine import score_event, high_case_command, load_policy
from .db import connect

core_app = FastAPI(title="BancoCloud Core LOCAL FIRST", docs_url=None, redoc_url=None)
fraud_app = FastAPI(title="BancoCloud Fraud LOCAL FIRST", docs_url=None, redoc_url=None)


def check_key(key):
    if not os.environ.get("DEMO_API_KEY") or key != os.environ["DEMO_API_KEY"]:
        raise HTTPException(401, "Missing or invalid demo key")


class Transfer(BaseModel):
    source_account: UUID
    destination_account: UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    device_ref: str | None = None
    beneficiary_ref: str | None = None


@core_app.get("/health")
@fraud_app.get("/health")
def health():
    with connect() as conn:
        conn.execute("SELECT 1").fetchone()
    return {"status": "ok"}


@core_app.get("/accounts")
def accounts(x_demo_key: str | None = Header(None)):
    check_key(x_demo_key)
    with connect() as conn:
        result = conn.execute("SELECT account_ref, balance FROM accounts ORDER BY account_ref LIMIT 10").fetchall()
    return [{"account_ref": str(ref), "balance": str(balance)} for ref, balance in result]


@core_app.post("/transfers")
def transfer(request: Transfer, idempotency_key: UUID = Header(...), x_demo_key: str | None = Header(None)):
    check_key(x_demo_key)
    request_hash = hashlib.sha256(json.dumps(request.model_dump(mode="json"),sort_keys=True).encode()).hexdigest()
    if request.source_account == request.destination_account:
        raise HTTPException(400, "Source and destination must differ")
    with connect() as conn:
        with conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (idempotency_key.int % (2**63),))
            existing = conn.execute("SELECT transaction_id,correlation_id,request_hash FROM transactions WHERE idempotency_key=%s", (idempotency_key,)).fetchone()
            if existing:
                if existing[2] != request_hash:
                    raise HTTPException(409,"Idempotency key already used with another request")
                return {"transaction_id": str(existing[0]), "correlation_id": str(existing[1]), "replay": True}
            ids = sorted((request.source_account, request.destination_account))
            locked = conn.execute("SELECT account_ref,customer_ref,balance,status FROM accounts WHERE account_ref IN (%s,%s) ORDER BY account_ref FOR UPDATE", ids).fetchall()
            acc = {x[0]: x for x in locked}
            if len(acc) != 2 or acc[request.source_account][3] != "ACTIVE" or acc[request.destination_account][3] != "ACTIVE":
                raise HTTPException(400, "Account missing or inactive")
            if acc[request.source_account][2] < request.amount:
                raise HTTPException(400, "Insufficient demo balance")
            customer_ref = acc[request.source_account][1]
            region = conn.execute("SELECT region FROM customers WHERE customer_ref=%s", (customer_ref,)).fetchone()[0]
            txid, eid, cid = uuid4(), uuid4(), uuid4()
            conn.execute("UPDATE accounts SET balance=balance-%s WHERE account_ref=%s", (request.amount, request.source_account))
            conn.execute("UPDATE accounts SET balance=balance+%s WHERE account_ref=%s", (request.amount, request.destination_account))
            conn.execute("INSERT INTO transactions(transaction_id,idempotency_key,request_hash,customer_ref,source_account,destination_account,amount,correlation_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (txid,idempotency_key,request_hash,customer_ref,request.source_account,request.destination_account,request.amount,cid))
            event = {"schema_version":"1.0","event_id":str(eid),"event_type":"TransactionPosted",
                     "event_time":datetime.now(timezone.utc).isoformat(),"transaction_id":str(txid),
                     "customer_ref":str(customer_ref),"account_ref":str(request.source_account),
                     "transaction_type":"TRANSFER","amount":float(request.amount),"currency":"PEN",
                     "channel":"API","authentication_method":"SESSION","transaction_status":"POSTED",
                     "device_ref":request.device_ref,"beneficiary_ref":request.beneficiary_ref,
                     "location":{"country":"PE","region":region},"correlation_id":str(cid),"source_system":"core-simulator"}
            validate("transaction", event)
            conn.execute("INSERT INTO outbox_events(event_id,transaction_id,payload) VALUES (%s,%s,%s::jsonb)", (eid,txid,json.dumps(event)))
    return {"transaction_id":str(txid),"correlation_id":str(cid),"replay":False}


@fraud_app.post("/ingest")
def ingest(event: dict, x_demo_key: str | None = Header(None)):
    check_key(x_demo_key)
    try:
        validate("transaction", event)
    except Exception:
        raise HTTPException(422, "Transaction contract invalid") from None
    with connect() as conn:
        with conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (UUID(event["transaction_id"]).int % (2**63),))
            existing = conn.execute("SELECT score_payload FROM fraud_scores WHERE transaction_id=%s", (event["transaction_id"],)).fetchone()
            if existing:
                return {"score":existing[0],"replay":True}
            policy = load_policy(os.environ.get("POLICY_PATH") or None) if os.environ.get("POLICY_PATH") else load_policy()
            history = [x[0] for x in conn.execute("SELECT event_payload FROM processed_events WHERE customer_ref=%s AND event_time < %s ORDER BY event_time DESC", (event["customer_ref"], event["event_time"]))]
            score = score_event(event, history, policy)
            conn.execute("INSERT INTO processed_events(event_id,transaction_id,event_time,customer_ref,device_ref,beneficiary_ref,event_payload) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING", (event["event_id"],event["transaction_id"],event["event_time"],event["customer_ref"],event.get("device_ref"),event.get("beneficiary_ref"),json.dumps(event)))
            conn.execute("INSERT INTO fraud_scores(event_id,transaction_id,score_payload) VALUES (%s,%s,%s::jsonb) ON CONFLICT DO NOTHING", (event["event_id"],event["transaction_id"],json.dumps(score)))
            command = high_case_command(score)
            if command:
                case_id = uuid5(NAMESPACE_URL, "case:" + str(command["command_id"]))
                conn.execute("INSERT INTO fraud_cases(case_id,command_id,transaction_id,policy_version,correlation_id,command_payload) VALUES (%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING", (case_id,command["command_id"],event["transaction_id"],score["policy_version"],event["correlation_id"],json.dumps(command)))
    return {"score":score,"replay":False}


@core_app.get("/cases")
def cases(x_demo_key: str | None = Header(None)):
    check_key(x_demo_key)
    with connect() as conn:
        rows = conn.execute("SELECT case_id,command_payload FROM fraud_cases ORDER BY created_at DESC LIMIT 100").fetchall()
    return [{"case_id":str(x),"evidence":y} for x,y in rows]


@core_app.post("/cases/{case_id}/decision")
def decide(case_id: UUID, decision: dict, x_demo_key: str | None = Header(None)):
    check_key(x_demo_key)
    try:
        validate("decision", decision)
    except Exception:
        raise HTTPException(422,"Analyst decision contract invalid") from None
    if decision["case_id"] != str(case_id):
        raise HTTPException(400,"Case ID mismatch")
    with connect() as conn:
        row = conn.execute("SELECT transaction_id,correlation_id FROM fraud_cases WHERE case_id=%s", (case_id,)).fetchone()
        if not row or (str(row[0]),str(row[1])) != (decision["transaction_id"],decision["correlation_id"]):
            raise HTTPException(400,"Case reference mismatch")
        conn.execute("INSERT INTO analyst_decisions(case_id,decision_payload) VALUES (%s,%s::jsonb) ON CONFLICT (case_id) DO UPDATE SET decision_payload=EXCLUDED.decision_payload", (case_id,json.dumps(decision)))
    return {"status":"recorded"}
