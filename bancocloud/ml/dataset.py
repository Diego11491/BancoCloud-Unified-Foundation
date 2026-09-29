"""Governed temporal dataset construction shared by ML experiments."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from bancocloud.engine import extract_features

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVENTS = ROOT / "data/synthetic/transaction_events.jsonl"
DEFAULT_LABELS = ROOT / "data/synthetic/fraud_labels.jsonl"

FORBIDDEN_INPUTS = {
    "fraud_label",
    "fraud_scenario",
    "score_riesgo",
    "alerta_sistema",
    "fraude_confirmado",
    "is_fraud",
    "label_timestamp",
    "label_source",
}

FEATURE_NAMES = (
    "log_amount",
    "tx_count_1m",
    "tx_count_5m",
    "tx_count_1h",
    "amount_sum_5m",
    "amount_vs_avg_30d",
    "amount_vs_avg_30d_missing",
    "amount_vs_median_30d",
    "amount_vs_median_30d_missing",
    "new_device",
    "new_device_missing",
    "device_age_days",
    "device_age_days_missing",
    "new_beneficiary",
    "new_beneficiary_missing",
    "prior_beneficiary_tx_count",
    "prior_beneficiary_tx_count_missing",
    "channel_changed",
    "channel_changed_missing",
    "hour_deviation",
    "hour_deviation_missing",
)


def read_jsonl(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _optional(features: dict, name: str) -> tuple[float, float]:
    value = features[name]
    return 0.0 if value is None else float(value), 1.0 if value is None else 0.0


def build_temporal_matrix(
    events_path: str | Path = DEFAULT_EVENTS,
    labels_path: str | Path = DEFAULT_LABELS,
    *,
    include_metadata: bool = False,
) -> list[dict]:
    """Join labels only as targets and derive features from prior history."""

    events = read_jsonl(events_path)
    labels = read_jsonl(labels_path)
    event_ids = [row["transaction_id"] for row in events]
    label_ids = [row["transaction_id"] for row in labels]

    if len(set(event_ids)) != len(event_ids):
        raise ValueError("Duplicate transaction_id in events")
    if len(set(label_ids)) != len(label_ids):
        raise ValueError("Duplicate transaction_id in labels")

    missing = set(event_ids) - set(label_ids)
    extra = set(label_ids) - set(event_ids)
    if missing or extra:
        raise ValueError(
            f"Event/label mismatch: missing={len(missing)}, extra={len(extra)}"
        )

    labels_by_id = {}
    for label in labels:
        if label.get("is_fraud") not in (0, 1):
            raise ValueError("is_fraud must be binary")
        labels_by_id[label["transaction_id"]] = label

    ordered = sorted(
        events,
        key=lambda row: (_time(row["event_time"]), row["transaction_id"]),
    )
    history: defaultdict[str, list[dict]] = defaultdict(list)
    records = []

    for event in ordered:
        customer_history = history[event["customer_ref"]]
        derived = extract_features(event, customer_history)
        avg, avg_missing = _optional(derived, "amount_vs_avg_30d")
        med, med_missing = _optional(derived, "amount_vs_median_30d")
        new_device, new_device_missing = _optional(derived, "new_device")
        device_age, device_age_missing = _optional(derived, "device_age_days")
        new_beneficiary, new_beneficiary_missing = _optional(
            derived, "new_beneficiary"
        )
        beneficiary_count, beneficiary_count_missing = _optional(
            derived, "prior_beneficiary_tx_count"
        )
        channel_changed, channel_changed_missing = _optional(
            derived, "channel_changed"
        )
        hour_deviation, hour_deviation_missing = _optional(
            derived, "hour_deviation"
        )

        values = {
            "log_amount": math.log1p(event["amount"]),
            "tx_count_1m": float(derived["tx_count_1m"]),
            "tx_count_5m": float(derived["tx_count_5m"]),
            "tx_count_1h": float(derived["tx_count_1h"]),
            "amount_sum_5m": float(derived["amount_sum_5m"]),
            "amount_vs_avg_30d": avg,
            "amount_vs_avg_30d_missing": avg_missing,
            "amount_vs_median_30d": med,
            "amount_vs_median_30d_missing": med_missing,
            "new_device": new_device,
            "new_device_missing": new_device_missing,
            "device_age_days": device_age,
            "device_age_days_missing": device_age_missing,
            "new_beneficiary": new_beneficiary,
            "new_beneficiary_missing": new_beneficiary_missing,
            "prior_beneficiary_tx_count": beneficiary_count,
            "prior_beneficiary_tx_count_missing": beneficiary_count_missing,
            "channel_changed": channel_changed,
            "channel_changed_missing": channel_changed_missing,
            "hour_deviation": hour_deviation,
            "hour_deviation_missing": hour_deviation_missing,
        }
        if set(values) != set(FEATURE_NAMES) or set(values) & FORBIDDEN_INPUTS:
            raise RuntimeError("Feature allowlist violation")

        label = labels_by_id[event["transaction_id"]]
        record = {
            "transaction_id": event["transaction_id"],
            "event_time": event["event_time"],
            "is_fraud": int(label["is_fraud"]),
            "label_source": label.get("label_source", "unknown"),
            "features": values,
        }
        if include_metadata:
            record["customer_ref"] = event["customer_ref"]
            record["fraud_scenario"] = label.get("fraud_scenario", "unknown")
        records.append(record)
        customer_history.append(event)

    return records


def temporal_partitions(
    size: int,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
) -> dict[str, tuple[int, int]]:
    if size < 10 or not 0 < train_ratio < 1 or not 0 < validation_ratio < 1:
        raise ValueError("Invalid temporal split")
    train_end = int(size * train_ratio)
    validation_end = train_end + int(size * validation_ratio)
    if validation_end >= size:
        raise ValueError("Temporal split leaves no test rows")
    return {
        "train": (0, train_end),
        "validation": (train_end, validation_end),
        "test": (validation_end, size),
    }


def matrix(records: list[dict], bounds: tuple[int, int]):
    start, end = bounds
    x = [
        [record["features"][name] for name in FEATURE_NAMES]
        for record in records[start:end]
    ]
    y = [record["is_fraud"] for record in records[start:end]]
    if set(y) != {0, 1}:
        raise ValueError("Every temporal partition must contain both classes")
    return x, y


def write_matrix(
    records: list[dict],
    partitions: dict[str, tuple[int, int]],
    path: str | Path,
) -> str:
    split_by_index = {}
    for name, (start, end) in partitions.items():
        split_by_index.update({index: name for index in range(start, end)})

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(
            target,
            fieldnames=[
                "transaction_id",
                "event_time",
                "split",
                "is_fraud",
                *FEATURE_NAMES,
            ],
        )
        writer.writeheader()
        for index, record in enumerate(records):
            writer.writerow(
                {
                    "transaction_id": record["transaction_id"],
                    "event_time": record["event_time"],
                    "split": split_by_index[index],
                    "is_fraud": record["is_fraud"],
                    **record["features"],
                }
            )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dataset_diagnostics(records: list[dict]) -> dict:
    customers = {record["customer_ref"] for record in records}
    scenarios: dict[str, int] = {}
    for record in records:
        scenario = record["fraud_scenario"]
        scenarios[scenario] = scenarios.get(scenario, 0) + 1
    first = _time(records[0]["event_time"])
    last = _time(records[-1]["event_time"])
    return {
        "rows": len(records),
        "positives": sum(record["is_fraud"] for record in records),
        "positive_rate": round(
            sum(record["is_fraud"] for record in records) / len(records), 6
        ),
        "customers": len(customers),
        "events_per_customer": round(len(records) / len(customers), 6),
        "time_span_days": round((last - first).total_seconds() / 86400, 6),
        "scenarios": dict(sorted(scenarios.items())),
    }
