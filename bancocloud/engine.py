import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from uuid import uuid5, NAMESPACE_URL

from .contracts import validate

DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "config/policy.v1.json"


def load_policy(path=DEFAULT_POLICY):
    policy = json.loads(Path(path).read_text())
    assert 0 < policy["medium_threshold"] < policy["high_threshold"] <= 1
    assert all(0 <= x <= 1 for x in policy["rule_weights"].values())
    return policy


def extract_features(event, history=(), rapid_window_seconds=300):
    """Use prior posted facts only; missing evidence stays unknown (None)."""
    validate("transaction", event)
    t = datetime.fromisoformat(event["event_time"].replace("Z", "+00:00")).astimezone(timezone.utc)
    previous = []
    seen = set()
    for row in history:
        if row["customer_ref"] != event["customer_ref"] or row["event_id"] in seen:
            continue
        earlier = datetime.fromisoformat(row["event_time"].replace("Z", "+00:00")).astimezone(timezone.utc)
        if earlier >= t:
            continue
        seen.add(row["event_id"])
        previous.append((row, (t - earlier).total_seconds(), earlier))

    counts = {seconds: sum(age <= seconds for _, age, _ in previous) for seconds in (60, 300, 3600)}
    recent = [row for row, age, _ in previous if age <= 300 and row.get("currency") == event["currency"]]
    amounts = [row["amount"] for row, age, _ in previous
               if age <= 30 * 86400 and row.get("currency") == event["currency"]]
    device = event.get("device_ref")
    known_devices = {row.get("device_ref") for row, _, _ in previous if row.get("device_ref")}
    device_times = [earlier for row, _, earlier in previous if device and row.get("device_ref") == device]
    beneficiary = event.get("beneficiary_ref")
    known_beneficiaries = {row.get("beneficiary_ref") for row, _, _ in previous if row.get("beneficiary_ref")}
    channel_counts = Counter(row["channel"] for row, _, _ in previous)
    hour_counts = Counter(earlier.hour for _, _, earlier in previous)

    def unique_mode(counts, minimum=1):
        if not counts:
            return None
        top = counts.most_common()
        return top[0][0] if len(previous) >= minimum and (len(top) == 1 or top[0][1] > top[1][1]) else None

    usual_channel = unique_mode(channel_counts, minimum=3)
    usual_hour = unique_mode(hour_counts, minimum=3)
    hour_distance = abs(t.hour - usual_hour) if usual_hour is not None else None
    return {
        "tx_count_1m": counts[60], "tx_count_5m": counts[300], "tx_count_1h": counts[3600],
        "tx_count_rapid_window": sum(age <= rapid_window_seconds for _, age, _ in previous),
        "amount_sum_5m": round(sum(row["amount"] for row in recent), 2),
        "amount_vs_avg_30d": event["amount"] / (sum(amounts) / len(amounts)) if amounts else None,
        "amount_vs_median_30d": event["amount"] / median(amounts) if amounts else None,
        "new_device": device not in known_devices if device and known_devices else None,
        "device_age_days": (t - min(device_times)).total_seconds() / 86400 if device_times else None,
        "new_beneficiary": beneficiary not in known_beneficiaries if beneficiary and known_beneficiaries else None,
        "prior_beneficiary_tx_count": sum(row.get("beneficiary_ref") == beneficiary for row, _, _ in previous)
        if beneficiary and known_beneficiaries else None,
        "usual_channel": usual_channel,
        "channel_changed": event["channel"] != usual_channel if usual_channel is not None else None,
        "hour_deviation": min(hour_distance, 24 - hour_distance) if hour_distance is not None else None,
    }


def score_event(event, history=(), policy=None, now=None):
    p = policy or load_policy()
    features = extract_features(event, history, p["rapid_window_seconds"])
    signals = {
        "large_amount": event["currency"] == "PEN" and event["amount"] >= p["large_amount_pen"],
        "new_device": features["new_device"] is True,
        "new_beneficiary": features["new_beneficiary"] is True,
        "rapid_activity": features["tx_count_rapid_window"] >= p["rapid_count"],
    }
    value = min(1.0, round(sum(p["rule_weights"][k] for k, active in signals.items() if active), 4))
    level = "HIGH" if value >= p["high_threshold"] else "MEDIUM" if value >= p["medium_threshold"] else "LOW"
    result = {
        "schema_version": "1.0", "transaction_id": event["transaction_id"], "event_id": event["event_id"],
        "scored_at": (now or datetime.now(timezone.utc)).isoformat(), "risk_score": value,
        "risk_level": level, "reason_codes": [k.upper() for k, active in signals.items() if active],
        "model_version": p["model_version"], "feature_version": p["feature_version"],
        "policy_version": p["policy_version"], "correlation_id": event["correlation_id"],
    }
    return validate("score", result)


def high_case_command(score, now=None):
    validate("score", score)
    if score["risk_level"] != "HIGH":
        return None
    result = {
        "schema_version": "1.0", "command_id": str(uuid5(NAMESPACE_URL, score["transaction_id"] + ":" + score["policy_version"])),
        "transaction_id": score["transaction_id"], "risk_score": score["risk_score"],
        "risk_level": "HIGH", "reason_codes": score["reason_codes"],
        "model_version": score["model_version"], "policy_version": score["policy_version"],
        "correlation_id": score["correlation_id"], "created_at": (now or datetime.now(timezone.utc)).isoformat(),
    }
    return validate("case", result)
