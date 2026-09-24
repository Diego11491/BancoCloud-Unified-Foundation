import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from bancocloud.ml_baseline import (
    FEATURE_NAMES,
    FORBIDDEN_INPUTS,
    build_temporal_matrix,
    run_baseline,
    temporal_partitions,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LABELS = (
    ROOT
    / "data/synthetic/fraud_labels.jsonl"
)

SKLEARN_AVAILABLE = (
    importlib.util.find_spec("sklearn")
    is not None
)


class MlBaselineTests(unittest.TestCase):
    def test_matrix_is_temporal_and_label_fields_are_not_features(
        self,
    ):
        records = build_temporal_matrix()

        self.assertEqual(
            len(records),
            10000,
        )

        self.assertEqual(
            sum(
                row["is_fraud"]
                for row in records
            ),
            323,
        )

        self.assertEqual(
            set(FEATURE_NAMES).intersection(
                FORBIDDEN_INPUTS
            ),
            set(),
        )

        times = [
            row["event_time"]
            for row in records
        ]

        self.assertEqual(
            times,
            sorted(times),
        )

        self.assertEqual(
            set(records[0]),
            {
                "transaction_id",
                "event_time",
                "is_fraud",
                "label_source",
                "features",
            },
        )

        self.assertEqual(
            set(records[0]["features"]),
            set(FEATURE_NAMES),
        )

    def test_missing_or_extra_label_is_rejected(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp:
            labels = (
                Path(temp)
                / "labels.jsonl"
            )

            with DEFAULT_LABELS.open(
                encoding="utf-8"
            ) as source:
                rows = source.readlines()

            labels.write_text(
                "".join(rows[:-1]),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "Event/label mismatch",
            ):
                build_temporal_matrix(
                    labels_path=labels
                )

    def test_temporal_partitions_are_contiguous(
        self,
    ):
        split = temporal_partitions(10000)

        self.assertEqual(
            split,
            {
                "train": (0, 7000),
                "validation": (
                    7000,
                    8500,
                ),
                "test": (
                    8500,
                    10000,
                ),
            },
        )

    @unittest.skipUnless(
        SKLEARN_AVAILABLE,
        "Install requirements-ml.txt",
    )
    def test_offline_candidate_keeps_rules_fallback(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp:
            with redirect_stdout(
                io.StringIO()
            ):
                report = run_baseline(
                    matrix_path=(
                        Path(temp)
                        / "matrix.csv"
                    ),
                    report_path=(
                        Path(temp)
                        / "report.json"
                    ),
                )

        self.assertEqual(
            report["status"],
            "OFFLINE_CANDIDATE_NOT_AUTHORIZED",
        )

        self.assertEqual(
            report[
                "online_fallback_model_version"
            ],
            "rules-only-v1",
        )

        self.assertEqual(
            report["leakage_checks"][
                "forbidden_feature_intersection"
            ],
            [],
        )

        self.assertEqual(
            report["split"]["train"]["rows"],
            7000,
        )

        self.assertEqual(
            report["split"]["validation"][
                "rows"
            ],
            1500,
        )

        self.assertEqual(
            report["split"]["test"]["rows"],
            1500,
        )


if __name__ == "__main__":
    unittest.main()