"""CLI for challenge-set generation and offline multi-model benchmarking."""

from __future__ import annotations

import argparse
from pathlib import Path

from bancocloud.ml.benchmark import DEFAULT_MATRIX, DEFAULT_REPORT, run_benchmark
from bancocloud.ml.challenge import DEFAULT_OUTPUT, generate_challenge


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--events", type=int, default=10000)
    parser.add_argument("--active-customers", type=int, default=500)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--seed", type=int, default=20260929)
    args = parser.parse_args()

    generated = generate_challenge(
        output_dir=args.output,
        count=args.events,
        active_customers=args.active_customers,
        days=args.days,
        seed=args.seed,
    )
    run_benchmark(
        generated["events_path"],
        generated["labels_path"],
        matrix_path=args.matrix,
        report_path=args.report,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
