"""Binary fraud metrics and validation-only threshold selection."""

from __future__ import annotations


def _operating_point(y_true, probabilities, threshold: float) -> dict:
    from sklearn.metrics import confusion_matrix, precision_score, recall_score

    predictions = [int(value >= threshold) for value in probabilities]
    tn, fp, fn, tp = confusion_matrix(
        y_true, predictions, labels=[0, 1]
    ).ravel()
    return {
        "threshold": round(float(threshold), 6),
        "precision": round(
            float(precision_score(y_true, predictions, zero_division=0)), 6
        ),
        "recall": round(
            float(recall_score(y_true, predictions, zero_division=0)), 6
        ),
        "fpr": round(float(fp / (fp + tn)), 6),
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
    }


def binary_metrics(y_true, probabilities, threshold: float = 0.5) -> dict:
    from sklearn.calibration import calibration_curve
    from sklearn.metrics import (
        average_precision_score,
        brier_score_loss,
    )

    operating_point = _operating_point(y_true, probabilities, threshold)
    observed, predicted = calibration_curve(
        y_true, probabilities, n_bins=5, strategy="quantile"
    )
    return {
        "rows": len(y_true),
        "positives": int(sum(y_true)),
        **operating_point,
        "pr_auc": round(float(average_precision_score(y_true, probabilities)), 6),
        "brier_score": round(float(brier_score_loss(y_true, probabilities)), 6),
        "calibration_bins": [
            {
                "mean_probability": round(float(probability), 6),
                "observed_fraction": round(float(fraction), 6),
            }
            for probability, fraction in zip(predicted, observed)
        ],
    }


def select_threshold(
    y_validation,
    probabilities,
    *,
    max_fpr: float = 0.02,
    min_precision: float = 0.20,
) -> tuple[float, dict]:
    """Choose a threshold without looking at the test partition.

    Within the operational constraints, prioritize recall, then precision, then
    the lower false-positive rate. If no threshold meets the constraints, use a
    documented fallback utility instead of silently reading the test results.
    """

    candidates = sorted({0.0, 0.5, 1.0, *(float(value) for value in probabilities)})
    evaluated = [
        _operating_point(y_validation, probabilities, value) for value in candidates
    ]
    feasible = [
        row
        for row in evaluated
        if row["fpr"] <= max_fpr and row["precision"] >= min_precision
    ]
    if feasible:
        chosen = max(
            feasible,
            key=lambda row: (
                row["recall"],
                row["precision"],
                -row["fpr"],
                row["threshold"],
            ),
        )
        rule = "maximize_recall_subject_to_validation_constraints"
    else:
        chosen = max(
            evaluated,
            key=lambda row: (
                row["recall"] - 5 * row["fpr"],
                row["precision"],
                row["threshold"],
            ),
        )
        rule = "fallback_validation_utility"
    return chosen["threshold"], {
        "rule": rule,
        "max_fpr": max_fpr,
        "min_precision": min_precision,
        "evaluated_thresholds": len(evaluated),
    }
