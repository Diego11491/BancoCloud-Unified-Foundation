"""Build reproducible LOCAL FIRST Gold datasets for Power BI.

The module reuses the validated cold-path projection and never participates in
transaction authorization or online fraud scoring.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .cold import project
from .engine import high_case_command, score_event


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVENTS = ROOT / "data/synthetic/transaction_events.jsonl"
DEFAULT_LABELS = ROOT / "data/synthetic/fraud_labels.jsonl"
DEFAULT_CUSTOMERS = ROOT / "data/synthetic/customer_seed.jsonl"
DEFAULT_OUTPUT = ROOT / "data/quality/lake"

CUSTOMER_FIELDS = (
    "customer_ref",
    "account_ref",
    "departamento",
    "app_preferida",
    "tipo_operacion_frecuente",
    "monto_promedio_transaccion",
    "frecuencia_transacciones",
)
TRANSACTION_FIELDS = (
    "transaction_id",
    "event_id",
    "customer_ref",
    "account_ref",
    "date_key",
    "event_time",
    "transaction_type",
    "amount",
    "currency",
    "channel",
    "authentication_method",
    "transaction_status",
    "country",
    "region",
    "correlation_id",
)
EVALUATION_FIELDS = (
    "transaction_id",
    "event_id",
    "date_key",
    "customer_ref",
    "risk_score",
    "risk_level",
    "reason_codes",
    "model_version",
    "feature_version",
    "policy_version",
    "is_fraud",
    "fraud_scenario",
    "label_timestamp",
    "label_source",
    "correlation_id",
)
CASE_FIELDS = (
    "case_id",
    "command_id",
    "transaction_id",
    "date_key",
    "risk_score",
    "risk_level",
    "reason_codes",
    "model_version",
    "policy_version",
    "correlation_id",
    "created_at",
)


def _rows(path):
    with Path(path).open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                yield line_number, json.loads(line)
            except json.JSONDecodeError as exc:
                yield line_number, {"_parse_error": str(exc)}


def _write_csv(path, fieldnames, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _reject(target, dataset, line_number, reason, reference=None):
    target.write(json.dumps({
        "dataset": dataset,
        "line": line_number,
        "reference": reference,
        "reason": reason,
    }, ensure_ascii=False) + "\n")


def _required_text(row, fields):
    return all(isinstance(row.get(field), str) and row[field].strip() for field in fields)


def _load_customers(path, quarantine):
    customers = {}
    accounts = set()
    rejected = 0
    for line_number, row in _rows(path):
        reference = row.get("customer_ref")
        if not _required_text(row, ("customer_ref", "account_ref", "departamento")):
            _reject(quarantine, "customer_seed", line_number, "missing_required_customer_field", reference)
            rejected += 1
            continue
        if reference in customers or row["account_ref"] in accounts:
            _reject(quarantine, "customer_seed", line_number, "duplicate_customer_or_account", reference)
            rejected += 1
            continue
        customers[reference] = row
        accounts.add(row["account_ref"])
    return customers, rejected


def _load_labels(path, quarantine):
    labels = {}
    rejected = 0
    for line_number, row in _rows(path):
        reference = row.get("transaction_id")
        if not _required_text(row, ("transaction_id", "fraud_scenario", "label_timestamp", "label_source")):
            _reject(quarantine, "fraud_labels", line_number, "missing_required_label_field", reference)
            rejected += 1
            continue
        if row.get("is_fraud") not in (0, 1):
            _reject(quarantine, "fraud_labels", line_number, "is_fraud_must_be_binary", reference)
            rejected += 1
            continue
        if reference in labels:
            _reject(quarantine, "fraud_labels", line_number, "duplicate_transaction_label", reference)
            rejected += 1
            continue
        labels[reference] = row
    return labels, rejected


def _event_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build_power_bi_gold(
    events_path=DEFAULT_EVENTS,
    labels_path=DEFAULT_LABELS,
    customers_path=DEFAULT_CUSTOMERS,
    out_dir=DEFAULT_OUTPUT,
    expected_events=10000,
):
    """Project Bronze/Silver, then publish pseudonymous dimensional Gold CSVs."""
    out = Path(out_dir)
    cold_counts = project(events_path, out)
    gold = out / "gold"
    gold.mkdir(parents=True, exist_ok=True)
    quarantine_path = out / "quarantine/bi_rejected.jsonl"
    quarantine_path.parent.mkdir(parents=True, exist_ok=True)

    with quarantine_path.open("w", encoding="utf-8") as quarantine:
        customers, rejected_customers = _load_customers(customers_path, quarantine)
        labels, rejected_labels = _load_labels(labels_path, quarantine)

        events = [row for _, row in _rows(out / "silver/events.jsonl")]
        event_ids = {event["transaction_id"] for event in events}
        orphan_labels = 0
        for transaction_id in sorted(set(labels) - event_ids):
            _reject(quarantine, "fraud_labels", None, "label_without_transaction", transaction_id)
            orphan_labels += 1

        valid_events = []
        orphan_customers = 0
        missing_labels = 0
        for event in events:
            transaction_id = event["transaction_id"]
            if event["customer_ref"] not in customers:
                _reject(quarantine, "transaction_events", None, "transaction_without_customer", transaction_id)
                orphan_customers += 1
                continue
            if transaction_id not in labels:
                _reject(quarantine, "transaction_events", None, "transaction_without_label", transaction_id)
                missing_labels += 1
            valid_events.append(event)

    customer_rows = [
        {field: customer.get(field) for field in CUSTOMER_FIELDS}
        for customer in sorted(customers.values(), key=lambda row: row["customer_ref"])
    ]
    _write_csv(gold / "dim_customer.csv", CUSTOMER_FIELDS, customer_rows)

    days = sorted({event["event_time"][:10] for event in valid_events})
    date_rows = []
    for day in days:
        value = datetime.fromisoformat(day)
        date_rows.append({
            "date_key": day.replace("-", ""),
            "date": day,
            "year": value.year,
            "month": value.month,
            "day": value.day,
            "weekday_number": value.isoweekday(),
            "weekday_name": value.strftime("%A"),
        })
    _write_csv(
        gold / "dim_date.csv",
        ("date_key", "date", "year", "month", "day", "weekday_number", "weekday_name"),
        date_rows,
    )

    transaction_rows = []
    aggregates = defaultdict(lambda: {"transaction_count": 0, "amount_total": 0.0})
    for event in sorted(valid_events, key=lambda row: (_event_time(row["event_time"]), row["transaction_id"])):
        location = event.get("location") or {}
        day = event["event_time"][:10]
        transaction_rows.append({
            **event,
            "date_key": day.replace("-", ""),
            "country": location.get("country"),
            "region": location.get("region"),
        })
        key = (day, event["channel"], event["currency"])
        aggregates[key]["transaction_count"] += 1
        aggregates[key]["amount_total"] += float(event["amount"])
    _write_csv(gold / "fact_transactions.csv", TRANSACTION_FIELDS, transaction_rows)

    aggregate_rows = [
        {
            "date_key": day.replace("-", ""),
            "date": day,
            "channel": channel,
            "currency": currency,
            "transaction_count": values["transaction_count"],
            "amount_total": round(values["amount_total"], 2),
        }
        for (day, channel, currency), values in sorted(aggregates.items())
    ]
    _write_csv(
        gold / "agg_transactions_by_day_channel.csv",
        ("date_key", "date", "channel", "currency", "transaction_count", "amount_total"),
        aggregate_rows,
    )

    history = defaultdict(list)
    evaluation_rows = []
    case_rows = []
    risk_levels = Counter()
    confusion = Counter({"tn": 0, "fp": 0, "fn": 0, "tp": 0})
    for event in sorted(valid_events, key=lambda row: (_event_time(row["event_time"]), row["transaction_id"])):
        timestamp = _event_time(event["event_time"])
        score = score_event(event, history[event["customer_ref"]], now=timestamp)
        history[event["customer_ref"]].append(event)
        label = labels.get(event["transaction_id"])
        risk_levels[score["risk_level"]] += 1
        is_fraud = label["is_fraud"] if label else None
        predicted = score["risk_level"] == "HIGH"
        if is_fraud is not None:
            confusion["tp" if predicted and is_fraud else
                      "fp" if predicted else
                      "fn" if is_fraud else "tn"] += 1
        day = event["event_time"][:10]
        evaluation_rows.append({
            **score,
            "date_key": day.replace("-", ""),
            "customer_ref": event["customer_ref"],
            "reason_codes": "|".join(score["reason_codes"]),
            "is_fraud": is_fraud,
            "fraud_scenario": label.get("fraud_scenario") if label else None,
            "label_timestamp": label.get("label_timestamp") if label else None,
            "label_source": label.get("label_source") if label else None,
        })
        command = high_case_command(score, now=timestamp)
        if command:
            case_rows.append({
                **command,
                "case_id": command["command_id"],
                "date_key": day.replace("-", ""),
                "reason_codes": "|".join(command["reason_codes"]),
            })

    _write_csv(gold / "fact_fraud_evaluations.csv", EVALUATION_FIELDS, evaluation_rows)
    _write_csv(gold / "fact_fraud_cases.csv", CASE_FIELDS, case_rows)

    bi_quarantine = rejected_customers + rejected_labels + orphan_labels + orphan_customers + missing_labels
    checks = {
        "expected_event_count": len(events) == expected_events,
        "all_events_have_customer": orphan_customers == 0,
        "all_events_have_one_label": missing_labels == 0 and orphan_labels == 0,
        "one_evaluation_per_transaction": len(evaluation_rows) == len(transaction_rows),
        "high_generates_one_case": len(case_rows) == risk_levels["HIGH"],
        "no_invalid_record_promoted": bi_quarantine == 0,
    }
    report = {
        "source": {
            "customers": len(customers),
            "events": len(events),
            "labels": len(labels),
            "fraud_labels_positive": sum(row["is_fraud"] for row in labels.values()),
        },
        "cold_path": cold_counts,
        "gold": {
            "dim_customer": len(customer_rows),
            "dim_date": len(date_rows),
            "fact_transactions": len(transaction_rows),
            "fact_fraud_evaluations": len(evaluation_rows),
            "fact_fraud_cases": len(case_rows),
            "agg_transactions_by_day_channel": len(aggregate_rows),
        },
        "risk_levels": dict(sorted(risk_levels.items())),
        "high_vs_fraud_label_confusion": dict(confusion),
        "quarantine": {
            "cold_events": cold_counts["quarantine"],
            "bi_records": bi_quarantine,
        },
        "checks": checks,
        "pass": all(checks.values()),
        "limitations": [
            "All records are synthetic and support an academic demonstration only.",
            "Fraud scores are a deterministic offline re-projection of the current rules policy.",
            "HIGH is a policy alert level and is not equivalent to the synthetic fraud label.",
        ],
    }
    (out / "bi_reconciliation.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--customers", type=Path, default=DEFAULT_CUSTOMERS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--expected-events", type=int, default=10000)
    args = parser.parse_args()
    result = build_power_bi_gold(
        events_path=args.events,
        labels_path=args.labels,
        customers_path=args.customers,
        out_dir=args.output,
        expected_events=args.expected_events,
    )
    raise SystemExit(0 if result["pass"] else 1)
