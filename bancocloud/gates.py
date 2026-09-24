"""Database gates for the 10k fixture and the transactional outbox."""
import argparse
import json
from pathlib import Path

from .db import connect


def run(expected=10000):
    sql = {
        "fixture_events": "SELECT count(*) FROM processed_events WHERE event_payload->>'source_system'='synthetic-generator'",
        "fixture_scores": "SELECT count(*) FROM fraud_scores s JOIN processed_events e ON e.event_id=s.event_id WHERE e.event_payload->>'source_system'='synthetic-generator'",
        "fixture_high": "SELECT count(*) FROM fraud_scores s JOIN processed_events e ON e.event_id=s.event_id WHERE e.event_payload->>'source_system'='synthetic-generator' AND s.score_payload->>'risk_level'='HIGH'",
        "fixture_cases": "SELECT count(*) FROM fraud_cases c JOIN processed_events e ON e.transaction_id=c.transaction_id WHERE e.event_payload->>'source_system'='synthetic-generator'",
        "medium_cases": "SELECT count(*) FROM fraud_cases c JOIN fraud_scores s ON s.transaction_id=c.transaction_id WHERE s.score_payload->>'risk_level' <> 'HIGH'",
        "bad_correlations": "SELECT count(*) FROM fraud_scores s JOIN processed_events e ON e.event_id=s.event_id WHERE s.score_payload->>'correlation_id' IS DISTINCT FROM e.event_payload->>'correlation_id'",
        "bad_case_correlations": "SELECT count(*) FROM fraud_cases c JOIN fraud_scores s ON s.transaction_id=c.transaction_id WHERE c.command_payload->>'correlation_id' IS DISTINCT FROM s.score_payload->>'correlation_id'",
        "missing_versions": "SELECT count(*) FROM fraud_scores WHERE nullif(score_payload->>'policy_version','') IS NULL OR nullif(score_payload->>'model_version','') IS NULL OR nullif(score_payload->>'feature_version','') IS NULL",
        "leaked_fields": "SELECT count(*) FROM processed_events WHERE event_payload ?| ARRAY['fraud_label','fraud_scenario','score_riesgo','alerta_sistema','fraude_confirmado']",
        "transactions_without_outbox": "SELECT count(*) FROM transactions t LEFT JOIN outbox_events o ON o.transaction_id=t.transaction_id WHERE o.event_id IS NULL",
        "pending_outbox": "SELECT count(*) FROM outbox_events WHERE published_at IS NULL",
        "duplicate_cases": "SELECT count(*) FROM (SELECT transaction_id,policy_version FROM fraud_cases GROUP BY 1,2 HAVING count(*)>1) d"
    }
    with connect() as conn:
        counts = {key:conn.execute(query).fetchone()[0] for key,query in sql.items()}
    checks = {
        "fixture_count": counts["fixture_events"] == expected,
        "one_score_per_fixture": counts["fixture_scores"] == expected,
        "high_generates_one_case": counts["fixture_high"] > 0 and counts["fixture_cases"] == counts["fixture_high"],
        "no_medium_cases": counts["medium_cases"] == 0,
        "correlation_integrity": counts["bad_correlations"] == 0 and counts["bad_case_correlations"] == 0,
        "version_metadata": counts["missing_versions"] == 0,
        "no_event_leakage": counts["leaked_fields"] == 0,
        "atomic_outbox": counts["transactions_without_outbox"] == 0,
        "publisher_drained": counts["pending_outbox"] == 0,
        "no_duplicate_cases": counts["duplicate_cases"] == 0,
    }
    report = {"expected_fixture_events":expected,"counts":counts,"checks":checks,"pass":all(checks.values())}
    print(json.dumps(report,indent=2),flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected",type=int,default=10000)
    args = parser.parse_args()
    raise SystemExit(0 if run(args.expected)["pass"] else 1)
