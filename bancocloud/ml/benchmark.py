"""Validation-selected offline benchmark for the challenge dataset."""

from __future__ import annotations

import json
import platform
import random
import time
from pathlib import Path

from .dataset import (
    FEATURE_NAMES,
    FORBIDDEN_INPUTS,
    ROOT,
    build_temporal_matrix,
    dataset_diagnostics,
    matrix,
    temporal_partitions,
    write_matrix,
)
from .metrics import binary_metrics, select_threshold

DEFAULT_REPORT = ROOT / "data/quality/ml_benchmark_report.json"
DEFAULT_MATRIX = ROOT / "data/quality/ml_benchmark_matrix.csv"


def candidate_models(seed: int = 42):
    from sklearn.dummy import DummyClassifier
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return {
        "dummy_prior": DummyClassifier(strategy="prior"),
        "logistic_regression": make_pipeline(
            StandardScaler(),
            LogisticRegression(
                class_weight="balanced", max_iter=2000, random_state=seed
            ),
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=160,
            max_depth=10,
            min_samples_leaf=5,
            class_weight="balanced_subsample",
            n_jobs=1,
            random_state=seed,
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=160,
            max_leaf_nodes=15,
            learning_rate=0.07,
            min_samples_leaf=20,
            class_weight="balanced",
            random_state=seed,
        ),
    }


def _timed_probabilities(model, values) -> tuple[list[float], float]:
    started = time.perf_counter()
    probabilities = model.predict_proba(values)[:, 1]
    elapsed_ms = (time.perf_counter() - started) * 1000
    return probabilities, elapsed_ms


def _evaluate_model(name, model, train, validation, test) -> dict:
    x_train, y_train = train
    x_validation, y_validation = validation
    x_test, y_test = test
    started = time.perf_counter()
    model.fit(x_train, y_train)
    fit_seconds = time.perf_counter() - started
    validation_probability, validation_ms = _timed_probabilities(
        model, x_validation
    )
    threshold, threshold_selection = select_threshold(
        y_validation, validation_probability
    )
    test_probability, test_ms = _timed_probabilities(model, x_test)
    validation_metrics = binary_metrics(
        y_validation, validation_probability, threshold
    )
    test_metrics = binary_metrics(y_test, test_probability, threshold)
    return {
        "name": name,
        "selected_threshold": threshold,
        "threshold_selection": threshold_selection,
        "fit_seconds": round(fit_seconds, 6),
        "inference": {
            "validation_total_ms": round(validation_ms, 6),
            "test_total_ms": round(test_ms, 6),
            "test_ms_per_1000": round(test_ms / len(x_test) * 1000, 6),
        },
        "metrics": {
            "validation": validation_metrics,
            "test": test_metrics,
            "pr_auc_delta": round(
                abs(validation_metrics["pr_auc"] - test_metrics["pr_auc"]), 6
            ),
        },
    }


def _shuffled_label_control(train, validation, seed: int) -> dict:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    x_train, y_train = train
    x_validation, y_validation = validation
    shuffled = list(y_train)
    random.Random(seed).shuffle(shuffled)
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            class_weight="balanced", max_iter=2000, random_state=seed
        ),
    )
    model.fit(x_train, shuffled)
    probabilities = model.predict_proba(x_validation)[:, 1]
    pr_auc = float(average_precision_score(y_validation, probabilities))
    prevalence = sum(y_validation) / len(y_validation)
    upper_bound = max(0.15, prevalence * 3)
    return {
        "name": "shuffled_training_labels",
        "validation_pr_auc": round(pr_auc, 6),
        "validation_prevalence": round(prevalence, 6),
        "maximum_allowed_pr_auc": round(upper_bound, 6),
        "pass": pr_auc <= upper_bound,
    }


def run_benchmark(
    events_path,
    labels_path,
    *,
    matrix_path=DEFAULT_MATRIX,
    report_path=DEFAULT_REPORT,
    seed: int = 42,
) -> dict:
    import sklearn

    started = time.perf_counter()
    records = build_temporal_matrix(
        events_path, labels_path, include_metadata=True
    )
    partitions = temporal_partitions(len(records))
    train = matrix(records, partitions["train"])
    validation = matrix(records, partitions["validation"])
    test = matrix(records, partitions["test"])
    evaluations = [
        _evaluate_model(name, model, train, validation, test)
        for name, model in candidate_models(seed).items()
    ]
    eligible = [row for row in evaluations if row["name"] != "dummy_prior"]
    champion = max(
        eligible,
        key=lambda row: (
            row["metrics"]["validation"]["pr_auc"],
            row["metrics"]["validation"]["recall"],
            -row["metrics"]["validation"]["fpr"],
            -row["inference"]["validation_total_ms"],
        ),
    )
    negative_control = _shuffled_label_control(train, validation, seed)
    matrix_hash = write_matrix(records, partitions, matrix_path)
    report = {
        "status": "OFFLINE_CHAMPION_NOT_AUTHORIZED",
        "benchmark_version": "fraud-model-benchmark-v2",
        "candidate_model_version": f"{champion['name']}-challenge-v2",
        "online_fallback_model_version": "rules-only-v1",
        "feature_version": "student-features-v2",
        "selection_uses_test_partition": False,
        "dataset": {
            **dataset_diagnostics(records),
            "matrix_sha256": matrix_hash,
        },
        "split": {
            name: {
                "rows": end - start,
                "positives": sum(
                    record["is_fraud"] for record in records[start:end]
                ),
                "start_time": records[start]["event_time"],
                "end_time": records[end - 1]["event_time"],
            }
            for name, (start, end) in partitions.items()
        },
        "leakage_checks": {
            "forbidden_feature_intersection": sorted(
                set(FEATURE_NAMES) & FORBIDDEN_INPUTS
            ),
            "labels_used_only_as_target": True,
            "temporal_split": True,
            "threshold_selected_on_validation_only": True,
            "champion_selected_on_validation_only": True,
            "shuffled_label_control": negative_control,
        },
        "champion": champion["name"],
        "candidates": evaluations,
        "runtime": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "seed": seed,
            "elapsed_seconds": round(time.perf_counter() - started, 6),
        },
        "limitations": [
            "All records and labels are synthetic.",
            "The benchmark supports an academic comparison, not production authorization.",
            "No model artifact is promoted or loaded by online scoring.",
        ],
    }
    if report["leakage_checks"]["forbidden_feature_intersection"]:
        raise RuntimeError("Forbidden features reached the benchmark")
    if not negative_control["pass"]:
        raise RuntimeError("Shuffled-label negative control failed")

    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return report
