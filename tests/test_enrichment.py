import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from bancocloud.engine import extract_features, load_policy, score_event

ROOT = Path(__file__).resolve().parents[1]


class EnrichmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / "data/synthetic/transaction_events.jsonl").open() as source:
            cls.sample = json.loads(next(source))

    def event(self, when, **changes):
        return {**self.sample, "event_id": str(uuid4()), "transaction_id": str(uuid4()),
                "event_time": when.isoformat(), **changes}

    def test_windows_amounts_and_identity_are_based_on_prior_facts(self):
        now = datetime(2026, 9, 21, 1, 0, tzinfo=timezone.utc)
        current = self.event(now, amount=300, currency="PEN", device_ref="D2",
                             beneficiary_ref="B2", channel="WEB")
        old = self.event(now - timedelta(days=40), amount=10, device_ref="D2",
                         beneficiary_ref="B2", channel="MOBILE")
        rows = [
            old,
            self.event(now - timedelta(days=2), amount=100, device_ref="D1",
                       beneficiary_ref="B1", channel="MOBILE"),
            self.event(now - timedelta(seconds=3500), amount=200, device_ref="D1",
                       beneficiary_ref="B1", channel="MOBILE"),
            self.event(now - timedelta(seconds=240), amount=50, device_ref="D1",
                       beneficiary_ref="B1", channel="MOBILE"),
            self.event(now - timedelta(seconds=30), amount=900, currency="USD",
                       device_ref="D1", beneficiary_ref="B1", channel="MOBILE"),
            self.event(now - timedelta(seconds=30), amount=150, device_ref="D1",
                       beneficiary_ref="B1", channel="MOBILE"),
        ]
        rows += [rows[-1], current, self.event(now + timedelta(seconds=1)),
                 self.event(now - timedelta(seconds=15), customer_ref="another-customer")]
        features = extract_features(current, rows)
        self.assertEqual((features["tx_count_1m"], features["tx_count_5m"], features["tx_count_1h"]), (2, 3, 4))
        self.assertEqual(features["amount_sum_5m"], 200)
        self.assertAlmostEqual(features["amount_vs_avg_30d"], 300 / 125)
        self.assertEqual(features["amount_vs_median_30d"], 300 / 125)
        self.assertFalse(features["new_device"])
        self.assertFalse(features["new_beneficiary"])
        self.assertEqual(features["prior_beneficiary_tx_count"], 1)
        self.assertEqual(features["device_age_days"], 40)
        self.assertEqual(features["usual_channel"], "MOBILE")
        self.assertTrue(features["channel_changed"])
        self.assertEqual(features["hour_deviation"], 1)

    def test_unknowns_remain_unknown_and_labels_never_enter_scoring(self):
        now = datetime(2026, 9, 21, tzinfo=timezone.utc)
        current = self.event(now, amount=100, device_ref="D", beneficiary_ref="B")
        missing = extract_features(current)
        for name in ("amount_vs_avg_30d", "amount_vs_median_30d", "new_device",
                     "device_age_days", "new_beneficiary", "usual_channel",
                     "channel_changed", "hour_deviation"):
            self.assertIsNone(missing[name], name)
        prior = self.event(now - timedelta(days=1), device_ref=None, beneficiary_ref=None)
        self.assertIsNone(extract_features(current, [prior])["new_device"])
        known = self.event(now - timedelta(hours=1), device_ref="other", beneficiary_ref="other")
        features = extract_features(current, [prior, known])
        self.assertTrue(features["new_device"])
        self.assertTrue(features["new_beneficiary"])
        self.assertEqual(features["prior_beneficiary_tx_count"], 0)
        contaminated = [{**known, "fraud_label": True, "score_riesgo": 1,
                         "fraud_scenario": "ignored", "alerta_sistema": True}]
        self.assertEqual(score_event(current, [known], now=now),
                         score_event(current, contaminated, now=now))
        self.assertEqual(score_event(current, [known], now=now)["model_version"], "rules-only-v1")
        self.assertEqual(load_policy()["feature_version"], "student-features-v2")
        self.assertEqual(load_policy()["policy_version"], "student-rules-v2")
        usd = self.event(now, amount=5000, currency="USD")
        self.assertNotIn("LARGE_AMOUNT", score_event(usd, now=now)["reason_codes"])

    def test_midnight_and_tied_patterns_have_defined_behavior(self):
        now = datetime(2026, 9, 21, 0, 0, tzinfo=timezone.utc)
        current = self.event(now, channel="WEB", device_ref="D", beneficiary_ref="B")
        history = [self.event(now - timedelta(days=day, hours=1), channel="MOBILE")
                   for day in (1, 2, 3)]
        self.assertEqual(extract_features(current, history)["hour_deviation"], 1)
        tied = history[:2] + [self.event(now - timedelta(days=4), channel="WEB")]
        self.assertEqual(extract_features(current, tied)["usual_channel"], "MOBILE")
        tied = history[:2] + [self.event(now - timedelta(days=4), channel="WEB"),
                              self.event(now - timedelta(days=5), channel="WEB")]
        self.assertIsNone(extract_features(current, tied)["usual_channel"])

    def test_first_observation_can_be_more_than_100_events_ago(self):
        now = datetime(2026, 9, 21, tzinfo=timezone.utc)
        current = self.event(now, device_ref="original", beneficiary_ref="original")
        history = [self.event(now - timedelta(days=90), device_ref="original",
                              beneficiary_ref="original")]
        history += [self.event(now - timedelta(minutes=i + 1), device_ref="other",
                               beneficiary_ref="other") for i in range(120)]
        features = extract_features(current, history)
        self.assertEqual(features["device_age_days"], 90)
        self.assertFalse(features["new_device"])
        self.assertFalse(features["new_beneficiary"])

    def test_rapid_rule_uses_policy_window(self):
        now = datetime(2026, 9, 21, tzinfo=timezone.utc)
        current = self.event(now, amount=10, device_ref=None, beneficiary_ref=None)
        history = [self.event(now - timedelta(seconds=120)),
                   self.event(now - timedelta(seconds=240))]
        policy = {**load_policy(), "rapid_window_seconds": 180, "rapid_count": 2}
        self.assertEqual(extract_features(current, history, rapid_window_seconds=180)["tx_count_rapid_window"], 1)
        self.assertNotIn("RAPID_ACTIVITY", score_event(current, history, policy, now)["reason_codes"])
        self.assertIn("RAPID_ACTIVITY", score_event(current, history,
                        {**policy, "rapid_count": 1}, now)["reason_codes"])


if __name__ == "__main__":
    unittest.main()
