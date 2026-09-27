import json
from uuid import UUID

from bancocloud.infrastructure.postgres.connection import connect


class PostgresCaseRepository:
    def list_recent(self, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 100))
        with connect() as conn:
            rows = conn.execute(
                "SELECT case_id,command_payload FROM fraud_cases ORDER BY created_at DESC LIMIT %s",
                (limit,),
            ).fetchall()
        return [{"case_id": str(case_id), "evidence": evidence} for case_id, evidence in rows]

    def get_reference(self, case_id: UUID) -> tuple[str, str] | None:
        with connect() as conn:
            row = conn.execute(
                "SELECT transaction_id,correlation_id FROM fraud_cases WHERE case_id=%s",
                (case_id,),
            ).fetchone()
        return (str(row[0]), str(row[1])) if row else None

    def save_decision(self, case_id: UUID, decision: dict) -> None:
        with connect() as conn:
            conn.execute(
                "INSERT INTO analyst_decisions(case_id,decision_payload) VALUES (%s,%s::jsonb) "
                "ON CONFLICT (case_id) DO UPDATE SET decision_payload=EXCLUDED.decision_payload",
                (case_id, json.dumps(decision)),
            )
