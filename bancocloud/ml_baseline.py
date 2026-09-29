"""Compatibility facade for the original offline temporal ML baseline.

Dataset construction, metrics and training now live in ``bancocloud.ml``.
Existing imports and the command ``python -m bancocloud.ml_baseline`` remain
stable while new experiments use ``python -m bancocloud.ml_benchmark``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from bancocloud.ml.baseline import DEFAULT_MATRIX, DEFAULT_REPORT, run_baseline
from bancocloud.ml.dataset import (
    DEFAULT_EVENTS,
    DEFAULT_LABELS,
    FEATURE_NAMES,
    FORBIDDEN_INPUTS,
    build_temporal_matrix,
    matrix as _matrix,
    temporal_partitions,
)
from bancocloud.ml.metrics import binary_metrics as _metrics

__all__ = [
    "FEATURE_NAMES",
    "FORBIDDEN_INPUTS",
    "build_temporal_matrix",
    "run_baseline",
    "temporal_partitions",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    run_baseline(args.events, args.labels, args.matrix, args.report)


if __name__ == "__main__":
    main()
