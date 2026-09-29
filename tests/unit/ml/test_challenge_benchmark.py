import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from bancocloud.ml.benchmark import run_benchmark
from bancocloud.ml.challenge import FRAUD_SCENARIOS, generate_challenge


class MlChallengeTests(unittest.TestCase):
    def test_challenge_is_deterministic_and_contains_overlapping_scenarios(self):
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first"
            second = Path(temp) / "second"
            one = generate_challenge(
                output_dir=first,
                count=1200,
                active_customers=100,
                days=60,
                seed=123,
            )
            two = generate_challenge(
                output_dir=second,
                count=1200,
                active_customers=100,
                days=60,
                seed=123,
            )

            self.assertEqual(
                (first / "transaction_events.jsonl").read_bytes(),
                (second / "transaction_events.jsonl").read_bytes(),
            )
            self.assertEqual(
                (first / "fraud_labels.jsonl").read_bytes(),
                (second / "fraud_labels.jsonl").read_bytes(),
            )
            self.assertEqual(one["events"], 1200)
            self.assertEqual(one["time_span_days"], 60)
            self.assertGreaterEqual(one["active_customers"], 90)
            self.assertTrue(set(FRAUD_SCENARIOS).issubset(one["scenario_counts"]))
            self.assertIn("legitimate_high_amount", one["scenario_counts"])
            self.assertGreater(one["fraud_counts"]["1"], 0)
            self.assertEqual(one["fraud_counts"], two["fraud_counts"])

    def test_rejects_sparse_or_short_challenge_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "at least 1000"):
                generate_challenge(output_dir=temp, count=999)
            with self.assertRaisesRegex(ValueError, "at least 30 days"):
                generate_challenge(output_dir=temp, days=7)


class MlBenchmarkTests(unittest.TestCase):
    def test_benchmark_selects_champion_without_test_partition(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            generated = generate_challenge(
                output_dir=root / "challenge",
                count=2000,
                active_customers=120,
                days=60,
                seed=123,
            )
            with redirect_stdout(io.StringIO()):
                report = run_benchmark(
                    generated["events_path"],
                    generated["labels_path"],
                    matrix_path=root / "matrix.csv",
                    report_path=root / "report.json",
                    seed=123,
                )

            self.assertEqual(report["status"], "OFFLINE_CHAMPION_NOT_AUTHORIZED")
            self.assertEqual(report["online_fallback_model_version"], "rules-only-v1")
            self.assertNotEqual(report["champion"], "dummy_prior")
            self.assertFalse(report["selection_uses_test_partition"])
            self.assertEqual(
                report["leakage_checks"]["forbidden_feature_intersection"], []
            )
            self.assertTrue(
                report["leakage_checks"]["shuffled_label_control"]["pass"]
            )
            self.assertEqual(len(report["candidates"]), 4)
            for candidate in report["candidates"]:
                self.assertIn("selected_threshold", candidate)
                self.assertIn("test_ms_per_1000", candidate["inference"])


if __name__ == "__main__":
    unittest.main()
