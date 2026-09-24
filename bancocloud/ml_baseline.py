"""Offline temporal ML baseline. It never participates in transaction authorization."""
import argparse
import csv
import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .engine import extract_features

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVENTS = ROOT / "data/synthetic/transaction_events.jsonl"
DEFAULT_LABELS = ROOT / "data/synthetic/fraud_labels.jsonl"
DEFAULT_MATRIX = ROOT / "data/quality/ml_feature_matrix.csv"
DEFAULT_REPORT = ROOT / "data/quality/ml_baseline_report.json"

FORBIDDEN_INPUTS = {
    "fraud_label", "fraud_scenario", "score_riesgo", "alerta_sistema",
    "fraude_confirmado", "is_fraud", "label_timestamp", "label_source",
}

FEATURE_NAMES = (
    "log_amount",
    "tx_count_1m", "tx_count_5m", "tx_count_1h", "amount_sum_5m",
    "amount_vs_avg_30d", "amount_vs_avg_30d_missing",
    "amount_vs_median_30d", "amount_vs_median_30d_missing",
    "new_device", "new_device_missing",
    "device_age_days", "device_age_days_missing",
    "new_beneficiary", "new_beneficiary_missing",
    "prior_beneficiary_tx_count", "prior_beneficiary_tx_count_missing",
    "channel_changed", "channel_changed_missing",
    "hour_deviation", "hour_deviation_missing",
)


def _read_jsonl(path):
    with Path(path).open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def _time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _optional(features, name):
    value = features[name]
    return (
        0.0 if value is None else float(value),
        1.0 if value is None else 0.0,
    )


def build_temporal_matrix(
    events_path=DEFAULT_EVENTS,
    labels_path=DEFAULT_LABELS,
):
    events = _read_jsonl(events_path)
    labels = _read_jsonl(labels_path)

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
        key=lambda row: (
            _time(row["event_time"]),
            row["transaction_id"],
        ),
    )

    history = defaultdict(list)
    records = []

    for event in ordered:
        derived = extract_features(
            event,
            history[event["customer_ref"]],
        )

        avg, avg_missing = _optional(
            derived,
            "amount_vs_avg_30d",
        )
        med, med_missing = _optional(
            derived,
            "amount_vs_median_30d",
        )
        new_device, new_device_missing = _optional(
            derived,
            "new_device",
        )
        device_age, device_age_missing = _optional(
            derived,
            "device_age_days",
        )
        new_beneficiary, new_beneficiary_missing = _optional(
            derived,
            "new_beneficiary",
        )
        beneficiary_count, beneficiary_count_missing = _optional(
            derived,
            "prior_beneficiary_tx_count",
        )
        channel_changed, channel_changed_missing = _optional(
            derived,
            "channel_changed",
        )
        hour_deviation, hour_deviation_missing = _optional(
            derived,
            "hour_deviation",
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

        if (
            set(values) != set(FEATURE_NAMES)
            or set(values) & FORBIDDEN_INPUTS
        ):
            raise RuntimeError("Feature allowlist violation")

        label = labels_by_id[event["transaction_id"]]

        records.append(
            {
                "transaction_id": event["transaction_id"],
                "event_time": event["event_time"],
                "is_fraud": int(label["is_fraud"]),
                "label_source": label.get(
                    "label_source",
                    "unknown",
                ),
                "features": values,
            }
        )

        history[event["customer_ref"]].append(event)

    return records


def temporal_partitions(
    size,
    train_ratio=0.70,
    validation_ratio=0.15,
):
    if (
        size < 10
        or not 0 < train_ratio < 1
        or not 0 < validation_ratio < 1
    ):
        raise ValueError("Invalid temporal split")

    train_end = int(size * train_ratio)
    validation_end = (
        train_end
        + int(size * validation_ratio)
    )

    if validation_end >= size:
        raise ValueError(
            "Temporal split leaves no test rows"
        )

    return {
        "train": (0, train_end),
        "validation": (
            train_end,
            validation_end,
        ),
        "test": (
            validation_end,
            size,
        ),
    }


def _matrix(records, bounds):
    start, end = bounds

    x = [
        [
            record["features"][name]
            for name in FEATURE_NAMES
        ]
        for record in records[start:end]
    ]

    y = [
        record["is_fraud"]
        for record in records[start:end]
    ]

    if set(y) != {0, 1}:
        raise ValueError(
            "Every temporal partition must contain both classes"
        )

    return x, y


def _metrics(
    y_true,
    probabilities,
    threshold=0.5,
):
    from sklearn.calibration import calibration_curve
    from sklearn.metrics import (
        average_precision_score,
        brier_score_loss,
        confusion_matrix,
        precision_score,
        recall_score,
    )

    predictions = [
        int(value >= threshold)
        for value in probabilities
    ]

    tn, fp, fn, tp = confusion_matrix(
        y_true,
        predictions,
        labels=[0, 1],
    ).ravel()

    observed, predicted = calibration_curve(
        y_true,
        probabilities,
        n_bins=5,
        strategy="quantile",
    )

    return {
        "rows": len(y_true),
        "positives": int(sum(y_true)),
        "pr_auc": round(
            float(
                average_precision_score(
                    y_true,
                    probabilities,
                )
            ),
            6,
        ),
        "precision": round(
            float(
                precision_score(
                    y_true,
                    predictions,
                    zero_division=0,
                )
            ),
            6,
        ),
        "recall": round(
            float(
                recall_score(
                    y_true,
                    predictions,
                    zero_division=0,
                )
            ),
            6,
        ),
        "fpr": round(
            float(fp / (fp + tn)),
            6,
        ),
        "brier_score": round(
            float(
                brier_score_loss(
                    y_true,
                    probabilities,
                )
            ),
            6,
        ),
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
        "calibration_bins": [
            {
                "mean_probability": round(
                    float(probability),
                    6,
                ),
                "observed_fraction": round(
                    float(fraction),
                    6,
                ),
            }
            for probability, fraction
            in zip(predicted, observed)
        ],
    }


def _write_matrix(
    records,
    partitions,
    path,
):
    split_by_index = {}

    for name, (start, end) in partitions.items():
        split_by_index.update(
            {
                index: name
                for index in range(start, end)
            }
        )

    path = Path(path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as target:
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
                    "transaction_id": record[
                        "transaction_id"
                    ],
                    "event_time": record[
                        "event_time"
                    ],
                    "split": split_by_index[index],
                    "is_fraud": record["is_fraud"],
                    **record["features"],
                }
            )

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def run_baseline(
    events_path=DEFAULT_EVENTS,
    labels_path=DEFAULT_LABELS,
    matrix_path=DEFAULT_MATRIX,
    report_path=DEFAULT_REPORT,
):
    from sklearn.linear_model import (
        LogisticRegression,
    )
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import (
        StandardScaler,
    )

    started = time.perf_counter()

    records = build_temporal_matrix(
        events_path,
        labels_path,
    )

    partitions = temporal_partitions(
        len(records)
    )

    x_train, y_train = _matrix(
        records,
        partitions["train"],
    )

    x_validation, y_validation = _matrix(
        records,
        partitions["validation"],
    )

    x_test, y_test = _matrix(
        records,
        partitions["test"],
    )

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            class_weight="balanced",
            max_iter=2000,
            random_state=42,
        ),
    )

    model.fit(
        x_train,
        y_train,
    )

    validation_probability = (
        model.predict_proba(x_validation)[:, 1]
    )

    test_probability = (
        model.predict_proba(x_test)[:, 1]
    )

    coefficients = model.named_steps[
        "logisticregression"
    ].coef_[0]

    top_coefficients = sorted(
        (
            {
                "feature": name,
                "coefficient": round(
                    float(value),
                    6,
                ),
            }
            for name, value
            in zip(
                FEATURE_NAMES,
                coefficients,
            )
        ),
        key=lambda row: abs(
            row["coefficient"]
        ),
        reverse=True,
    )[:12]

    matrix_hash = _write_matrix(
        records,
        partitions,
        matrix_path,
    )

    label_sources = Counter(
        record["label_source"]
        for record in records
    )

    report = {
        "status": (
            "OFFLINE_CANDIDATE_NOT_AUTHORIZED"
        ),
        "candidate_model_version": (
            "logreg-temporal-baseline-v1"
        ),
        "online_fallback_model_version": (
            "rules-only-v1"
        ),
        "feature_version": (
            "student-features-v2"
        ),
        "dataset": {
            "rows": len(records),
            "positives": sum(
                record["is_fraud"]
                for record in records
            ),
            "label_sources": dict(
                sorted(label_sources.items())
            ),
            "matrix_sha256": matrix_hash,
        },
        "split": {
            name: {
                "rows": end - start,
                "start_time": records[start][
                    "event_time"
                ],
                "end_time": records[end - 1][
                    "event_time"
                ],
                "positives": sum(
                    record["is_fraud"]
                    for record
                    in records[start:end]
                ),
            }
            for name, (start, end)
            in partitions.items()
        },
        "leakage_checks": {
            "forbidden_feature_intersection": (
                sorted(
                    set(FEATURE_NAMES)
                    & FORBIDDEN_INPUTS
                )
            ),
            "labels_joined_only_by_transaction_id": True,
            "labels_used_only_as_target": True,
            "random_split_used": False,
        },
        "model": {
            "algorithm": (
                "logistic_regression"
            ),
            "class_weight": "balanced",
            "threshold": 0.5,
            "feature_names": list(
                FEATURE_NAMES
            ),
            "top_coefficients": (
                top_coefficients
            ),
        },
        "metrics": {
            "validation": _metrics(
                y_validation,
                validation_probability,
            ),
            "test": _metrics(
                y_test,
                test_probability,
            ),
        },
        "elapsed_seconds": round(
            time.perf_counter() - started,
            6,
        ),
        "limitations": [
            (
                "Labels and transactions are "
                "synthetic and scenario-generated."
            ),
            (
                "The candidate is not integrated "
                "into online scoring or authorization."
            ),
            (
                "Performance does not establish "
                "production fraud detection quality."
            ),
        ],
    }

    if report["leakage_checks"][
        "forbidden_feature_intersection"
    ]:
        raise RuntimeError(
            "Leakage detected"
        )

    report_path = Path(report_path)
    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            report,
            ensure_ascii=False,
        )
    )

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--events",
        type=Path,
        default=DEFAULT_EVENTS,
    )

    parser.add_argument(
        "--labels",
        type=Path,
        default=DEFAULT_LABELS,
    )

    parser.add_argument(
        "--matrix",
        type=Path,
        default=DEFAULT_MATRIX,
    )

    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
    )

    args = parser.parse_args()

    run_baseline(
        args.events,
        args.labels,
        args.matrix,
        args.report,
    )