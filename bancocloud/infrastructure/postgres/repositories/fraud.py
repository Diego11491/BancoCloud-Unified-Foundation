import json
from collections.abc import Callable
from uuid import NAMESPACE_URL, UUID, uuid5

from bancocloud.contracts import validate
from bancocloud.infrastructure.postgres.connection import connect
from bancocloud.repositories.fraud import FraudEvaluation


class PostgresFraudEvaluationStore:
    """LOCAL FIRST score store with transaction-level idempotency."""

    def evaluate_once(
        self,
        event: dict,
        evaluator: Callable[[list[dict]], dict],
    ) -> FraudEvaluation:
        transaction_id = UUID(event["transaction_id"])
        with connect() as conn:
            with conn.transaction():
                conn.execute(
                    "SELECT pg_advisory_xact_lock(%s)",
                    (transaction_id.int % (2**63),),
                )
                existing = conn.execute(
                    "SELECT score_payload FROM fraud_scores WHERE transaction_id=%s",
                    (transaction_id,),
                ).fetchone()
                if existing:
                    return FraudEvaluation(score=existing[0], replay=True)

                history = [
                    row[0]
                    for row in conn.execute(
                        "SELECT event_payload FROM processed_events "
                        "WHERE customer_ref=%s AND event_time < %s ORDER BY event_time DESC",
                        (event["customer_ref"], event["event_time"]),
                    )
                ]
                score = evaluator(history)
                conn.execute(
                    "INSERT INTO processed_events(event_id,transaction_id,event_time,customer_ref,"
                    "device_ref,beneficiary_ref,event_payload) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING",
                    (
                        event["event_id"],
                        event["transaction_id"],
                        event["event_time"],
                        event["customer_ref"],
                        event.get("device_ref"),
                        event.get("beneficiary_ref"),
                        json.dumps(event),
                    ),
                )
                conn.execute(
                    "INSERT INTO fraud_scores(event_id,transaction_id,score_payload) "
                    "VALUES (%s,%s,%s::jsonb)",
                    (event["event_id"], event["transaction_id"], json.dumps(score)),
                )
        return FraudEvaluation(score=score, replay=False)


class PostgresHighCaseSink:
    """Idempotent local substitute for Service Bus + Case Service."""

    def publish_high_case(self, command: dict) -> None:
        validate("case", command)
        case_id = uuid5(NAMESPACE_URL, "case:" + command["command_id"])
        with connect() as conn:
            conn.execute(
                "INSERT INTO fraud_cases(case_id,command_id,transaction_id,policy_version,"
                "correlation_id,command_payload) VALUES (%s,%s,%s,%s,%s,%s::jsonb) "
                "ON CONFLICT DO NOTHING",
                (
                    case_id,
                    command["command_id"],
                    command["transaction_id"],
                    command["policy_version"],
                    command["correlation_id"],
                    json.dumps(command),
                ),
            )
