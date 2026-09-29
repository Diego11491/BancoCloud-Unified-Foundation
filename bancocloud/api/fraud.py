import os

from fastapi import Depends, FastAPI, HTTPException

from bancocloud.api.dependencies import require_demo_key
from bancocloud.application.fraud_service import FraudContractError, FraudService
from bancocloud.engine import load_policy
from bancocloud.infrastructure.postgres.connection import connect
from bancocloud.infrastructure.postgres.repositories.fraud import (
    PostgresFraudEvaluationStore,
    PostgresHighCaseSink,
)


def configured_policy() -> dict:
    path = os.environ.get("POLICY_PATH")
    return load_policy(path) if path else load_policy()


app = FastAPI(title="BancoCloud Fraud Modular LOCAL FIRST", docs_url=None, redoc_url=None)
_secure = [Depends(require_demo_key)]
fraud_service = FraudService(
    PostgresFraudEvaluationStore(),
    PostgresHighCaseSink(),
    configured_policy,
)


@app.get("/health")
def health():
    with connect() as conn:
        conn.execute("SELECT 1").fetchone()
    return {"status": "ok"}


@app.post("/ingest", dependencies=_secure)
def ingest(event: dict):
    try:
        return fraud_service.ingest(event)
    except FraudContractError as exc:
        raise HTTPException(422, str(exc)) from exc


__all__ = ["app"]
