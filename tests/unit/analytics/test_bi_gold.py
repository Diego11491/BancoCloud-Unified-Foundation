import csv
import json
import tempfile
import unittest
from pathlib import Path

from bancocloud.bi import build_power_bi_gold


ROOT = Path(__file__).resolve().parents[3]


class PowerBIGoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name) / "lake"
        cls.report = build_power_bi_gold(
            events_path=ROOT / "data/synthetic/transaction_events.jsonl",
            labels_path=ROOT / "data/synthetic/fraud_labels.jsonl",
            customers_path=ROOT / "data/synthetic/customer_seed.jsonl",
            out_dir=cls.out,
            expected_events=10000,
        )

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_reconciles_full_fixture(self):
        self.assertTrue(self.report["pass"])
        self.assertEqual(self.report["source"]["customers"], 5960)
        self.assertEqual(self.report["source"]["events"], 10000)
        self.assertEqual(self.report["source"]["labels"], 10000)
        self.assertEqual(self.report["source"]["fraud_labels_positive"], 323)
        self.assertEqual(self.report["gold"]["fact_fraud_cases"], 93)
        self.assertEqual(self.report["quarantine"], {"cold_events": 0, "bi_records": 0})

    def test_publishes_power_bi_csvs_without_forbidden_identifiers(self):
        expected = {
            "dim_customer.csv",
            "dim_date.csv",
            "fact_transactions.csv",
            "fact_fraud_evaluations.csv",
            "fact_fraud_cases.csv",
            "agg_transactions_by_day_channel.csv",
        }
        self.assertEqual({path.name for path in (self.out / "gold").glob("*.csv")}, expected)
        with (self.out / "gold/fact_transactions.csv").open(encoding="utf-8-sig") as source:
            headers = next(csv.reader(source))
        self.assertNotIn("fraud_label", headers)
        self.assertNotIn("fraud_scenario", headers)
        self.assertNotIn("score_riesgo", headers)

    def test_reconciliation_file_matches_result(self):
        saved = json.loads((self.out / "bi_reconciliation.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, self.report)

    def test_invalid_label_is_quarantined_and_fails_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            with (ROOT / "data/synthetic/customer_seed.jsonl").open(encoding="utf-8") as source:
                customer = source.readline()
            with (ROOT / "data/synthetic/transaction_events.jsonl").open(encoding="utf-8") as source:
                event = source.readline()
            transaction_id = json.loads(event)["transaction_id"]
            invalid_label = json.dumps({
                "transaction_id": transaction_id,
                "is_fraud": 2,
                "fraud_scenario": "invalid-test",
                "label_timestamp": "2026-01-08T00:00:00+00:00",
                "label_source": "unit-test",
            }) + "\n"
            customers = temp / "customers.jsonl"
            events = temp / "events.jsonl"
            labels = temp / "labels.jsonl"
            customers.write_text(customer, encoding="utf-8")
            events.write_text(event, encoding="utf-8")
            labels.write_text(invalid_label, encoding="utf-8")
            report = build_power_bi_gold(events, labels, customers, temp / "lake", expected_events=1)
            reasons = (temp / "lake/quarantine/bi_rejected.jsonl").read_text(encoding="utf-8")
            self.assertFalse(report["pass"])
            self.assertIn("is_fraud_must_be_binary", reasons)
            self.assertIn("transaction_without_label", reasons)

    def test_data_quality_workflow_is_scoped_and_has_no_deployment(self):
        workflow = (ROOT / ".github/workflows/data-quality.yml").read_text(encoding="utf-8")
        self.assertIn("paths:", workflow)
        self.assertIn("python -m bancocloud.bi", workflow)
        self.assertNotIn("azure/login", workflow)
        self.assertNotIn("az deployment", workflow)


if __name__ == "__main__":
    unittest.main()
