"""Backward-compatible single-model baseline implementation."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

from .dataset import (
    FEATURE_NAMES,
    FORBIDDEN_INPUTS,
    ROOT,
    build_temporal_matrix,
    matrix,
    temporal_partitions,
    write_matrix,
)
from .metrics import binary_metrics

DEFAULT_MATRIX = ROOT / "data/quality/ml_feature_matrix.csv"
DEFAULT_REPORT = ROOT / "data/quality/ml_baseline_report.json"


def run_baseline(
    events_path=None,
    labels_path=None,
    matrix_path=DEFAULT_MATRIX,
    report_path=DEFAULT_REPORT,
):
    """Train the original interpretable candidate without authorizing it online."""

    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    started = time.perf_counter()
    dataset_kwargs = {}
    if events_path is not None:
        dataset_kwargs["events_path"] = events_path
    if labels_path is not None:
        dataset_kwargs["labels_path"] = labels_path
    records = build_temporal_matrix(**dataset_kwargs)
    partitions = temporal_partitions(len(records))
    x_train, y_train = matrix(records, partitions["train"])
    x_validation, y_validation = matrix(records, partitions["validation"])
    x_test, y_test = matrix(records, partitions["test"])

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            class_weight="balanced",
            max_iter=2000,
            random_state=42,
        ),
    )
    model.fit(x_train, y_train)
    validation_probability = model.predict_proba(x_validation)[:, 1]
    test_probability = model.predict_proba(x_test)[:, 1]
    coefficients = model.named_steps["logisticregression"].coef_[0]
    top_coefficients = sorted(
        (
            {"feature": name, "coefficient": round(float(value), 6)}
            for name, value in zip(FEATURE_NAMES, coefficients)
        ),
        key=lambda row: abs(row["coefficient"]),
        reverse=True,
    )[:12]
    matrix_hash = write_matrix(records, partitions, matrix_path)
    label_sources = Counter(record["label_source"] for record in records)

    report = {
        "status": "OFFLINE_CANDIDATE_NOT_AUTHORIZED",
        "candidate_model_version": "logreg-temporal-baseline-v1",
        "online_fallback_model_version": "rules-only-v1",
        "feature_version": "student-features-v2",
        "dataset": {
            "rows": len(records),
            "positives": sum(record["is_fraud"] for record in records),
            "label_sources": dict(sorted(label_sources.items())),
            "matrix_sha256": matrix_hash,
        },
        "split": {
            name: {
                "rows": end - start,
                "start_time": records[start]["event_time"],
                "end_time": records[end - 1]["event_time"],
                "positives": sum(
                    record["is_fraud"] for record in records[start:end]
                ),
            }
            for name, (start, end) in partitions.items()
        },
        "leakage_checks": {
            "forbidden_feature_intersection": sorted(
                set(FEATURE_NAMES) & FORBIDDEN_INPUTS
            ),
            "labels_joined_only_by_transaction_id": True,
            "labels_used_only_as_target": True,
            "random_split_used": False,
        },
        "model": {
            "algorithm": "logistic_regression",
            "class_weight": "balanced",
            "threshold": 0.5,
            "feature_names": list(FEATURE_NAMES),
            "top_coefficients": top_coefficients,
        },
        "metrics": {
            "validation": binary_metrics(y_validation, validation_probability, 0.5),
            "test": binary_metrics(y_test, test_probability, 0.5),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "limitations": [
            "Labels and transactions are synthetic and scenario-generated.",
            "The candidate is not integrated into online scoring or authorization.",
            "Performance does not establish production fraud detection quality.",
        ],
    }
    if report["leakage_checks"]["forbidden_feature_intersection"]:
        raise RuntimeError("Leakage detected")

    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return report
