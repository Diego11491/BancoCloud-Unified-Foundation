"""Deterministic synthetic challenge set for offline fraud experiments.

The original fixture is intentionally easy and remains the regression fixture.
This generator adds overlapping fraud and legitimate behaviours so model
comparison measures more than the original scenario recipe.
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from bancocloud.contracts import validate

from .dataset import ROOT, read_jsonl

DEFAULT_PROFILES = ROOT / "data/synthetic/customer_seed.jsonl"
DEFAULT_OUTPUT = ROOT / "data/quality/ml_challenge_v2"

FRAUD_SCENARIOS = (
    "amount_spike",
    "account_takeover",
    "rapid_new_beneficiary",
    "channel_shift",
)
LEGITIMATE_CHALLENGES = (
    "legitimate_high_amount",
    "legitimate_new_device",
    "legitimate_new_beneficiary",
)


def _identifier(kind: str, seed: int, index: int | str) -> str:
    return str(uuid5(NAMESPACE_URL, f"bancocloud-ml-v2:{seed}:{kind}:{index}"))


def _scenario(rng: random.Random) -> tuple[str, int]:
    value = rng.random()
    if value < 0.008:
        return "amount_spike", 1
    if value < 0.016:
        return "account_takeover", 1
    if value < 0.024:
        return "rapid_new_beneficiary", 1
    if value < 0.032:
        return "channel_shift", 1
    if value < 0.062:
        return "legitimate_high_amount", 0
    if value < 0.092:
        return "legitimate_new_device", 0
    if value < 0.122:
        return "legitimate_new_beneficiary", 0
    return "none", 0


def generate_challenge(
    profiles_path: str | Path = DEFAULT_PROFILES,
    output_dir: str | Path = DEFAULT_OUTPUT,
    *,
    count: int = 10000,
    seed: int = 20260929,
    active_customers: int = 500,
    days: int = 90,
) -> dict:
    """Write governed challenge events and labels and return reconciliation."""

    if count < 1000:
        raise ValueError("Challenge set requires at least 1000 events")
    if days < 30:
        raise ValueError("Challenge set must span at least 30 days")

    profiles = read_jsonl(profiles_path)
    if not profiles:
        raise ValueError("No customer profiles available")
    if not 50 <= active_customers <= len(profiles):
        raise ValueError("active_customers is outside the governed range")

    rng = random.Random(seed)
    active = rng.sample(profiles, active_customers)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    events_path = output_dir / "transaction_events.jsonl"
    labels_path = output_dir / "fraud_labels.jsonl"
    metadata_path = output_dir / "metadata.json"

    devices = {
        profile["customer_ref"]: _identifier("device", seed, profile["customer_ref"])
        for profile in active
    }
    beneficiaries = {
        profile["customer_ref"]: [
            _identifier("beneficiary", seed, f"{profile['customer_ref']}:{index}")
            for index in range(3)
        ]
        for profile in active
    }
    last_customer = None
    previous_event_time = None
    customer_events: defaultdict[str, int] = defaultdict(int)
    scenario_counts: Counter[str] = Counter()
    fraud_counts: Counter[int] = Counter()
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    total_seconds = days * 86400

    with events_path.open("w", encoding="utf-8") as events_file, labels_path.open(
        "w", encoding="utf-8"
    ) as labels_file:
        for index in range(count):
            scenario, is_fraud = _scenario(rng)
            if scenario == "rapid_new_beneficiary" and last_customer is not None:
                profile = last_customer
            else:
                profile = rng.choice(active)
            customer_ref = profile["customer_ref"]
            customer_events[customer_ref] += 1

            progress = index / max(1, count - 1)
            event_time = base + timedelta(seconds=int(progress * total_seconds))
            if scenario == "rapid_new_beneficiary" and previous_event_time is not None:
                event_time = previous_event_time + timedelta(minutes=1)
            elif previous_event_time is not None and event_time <= previous_event_time:
                event_time = previous_event_time + timedelta(seconds=1)
            typical_amount = max(10.0, float(profile["monto_promedio_transaccion"]))
            amount = typical_amount * rng.uniform(0.35, 2.25)
            device_ref = devices[customer_ref]
            beneficiary_ref = rng.choice(beneficiaries[customer_ref])
            preferred_channel = (
                "WEB" if profile["app_preferida"] == "Web Banking" else "MOBILE"
            )
            channel = preferred_channel

            if scenario == "amount_spike":
                amount = typical_amount * rng.uniform(3.5, 8.0)
            elif scenario == "account_takeover":
                amount = typical_amount * rng.uniform(1.3, 4.5)
                device_ref = _identifier("fraud-device", seed, index)
                beneficiary_ref = _identifier("fraud-beneficiary", seed, index)
                channel = "WEB" if preferred_channel == "MOBILE" else "MOBILE"
            elif scenario == "rapid_new_beneficiary":
                amount = typical_amount * rng.uniform(0.8, 3.0)
                beneficiary_ref = _identifier("fraud-beneficiary", seed, index)
            elif scenario == "channel_shift":
                amount = typical_amount * rng.uniform(0.7, 2.8)
                channel = rng.choice(["WEB", "MOBILE", "ATM"])
                if channel == preferred_channel:
                    channel = "ATM"
            elif scenario == "legitimate_high_amount":
                amount = typical_amount * rng.uniform(3.0, 7.5)
            elif scenario == "legitimate_new_device":
                device_ref = _identifier("legitimate-device", seed, index)
            elif scenario == "legitimate_new_beneficiary":
                beneficiary_ref = _identifier("legitimate-beneficiary", seed, index)

            transaction_id = _identifier("transaction", seed, index)
            event = {
                "schema_version": "1.0",
                "event_id": _identifier("event", seed, index),
                "event_type": "TransactionPosted",
                "event_time": event_time.isoformat(),
                "transaction_id": transaction_id,
                "customer_ref": customer_ref,
                "account_ref": profile["account_ref"],
                "transaction_type": rng.choice(
                    ["TRANSFER", "PAYMENT", "CARD_PURCHASE"]
                ),
                "amount": round(max(1.0, amount), 2),
                "currency": "PEN",
                "channel": channel,
                "authentication_method": rng.choice(
                    ["TOKEN", "OTP", "BIOMETRIC_MFA"]
                ),
                "transaction_status": "POSTED",
                "device_ref": device_ref,
                "beneficiary_ref": beneficiary_ref,
                "location": {
                    "country": "PE",
                    "region": str(profile["departamento"]),
                },
                "correlation_id": _identifier("correlation", seed, index),
                "source_system": "synthetic-ml-challenge-v2",
            }
            validate("transaction", event)
            label = {
                "transaction_id": transaction_id,
                "is_fraud": is_fraud,
                "fraud_scenario": scenario,
                "label_timestamp": (event_time + timedelta(days=7)).isoformat(),
                "label_source": "synthetic_challenge_v2",
            }
            events_file.write(json.dumps(event, ensure_ascii=False) + "\n")
            labels_file.write(json.dumps(label, ensure_ascii=False) + "\n")
            scenario_counts[scenario] += 1
            fraud_counts[is_fraud] += 1
            last_customer = profile
            previous_event_time = event_time

    metadata = {
        "dataset_version": "synthetic-ml-challenge-v2",
        "seed": seed,
        "events": count,
        "active_customers": len(customer_events),
        "configured_active_customers": active_customers,
        "time_span_days": days,
        "fraud_counts": {str(key): value for key, value in sorted(fraud_counts.items())},
        "scenario_counts": dict(sorted(scenario_counts.items())),
        "events_path": str(events_path),
        "labels_path": str(labels_path),
        "limitations": [
            "All records are synthetic and support an academic demonstration only.",
            "Scenario labels do not establish production fraud prevalence.",
            "External authentication and device-registration histories are not simulated.",
        ],
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return metadata
