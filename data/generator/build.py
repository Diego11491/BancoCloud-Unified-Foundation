"""Convert the attached workbook to anonymous profile seeds and deterministic demo events."""
import argparse
import hashlib
import json
import random
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import openpyxl

from bancocloud.contracts import validate

ROOT = Path(__file__).resolve().parents[2]
KEEP = ("departamento", "app_preferida", "tipo_operacion_frecuente", "monto_promedio_transaccion", "frecuencia_transacciones")
EXCLUDE = ("alerta_sistema", "fraude_confirmado", "score_riesgo", "historial_suspicious", "dispositivo_nuevo", "fallas_autenticacion", "ubicacion_inusual", "horario_inusual", "fecha_registro")
TYPE = {"Pago de Préstamos": "LOAN_PAYMENT", "Pago de Tarjeta de Crédito": "PAYMENT", "Compras Online": "CARD_PURCHASE", "Pago de Servicios": "PAYMENT", "Retiro sin Tarjeta": "CASH_WITHDRAWAL", "Transferencia Mismo Banco": "TRANSFER", "Transferencia Interbancaria": "TRANSFER", "Depósito": "DEPOSIT"}


def identifier(kind, value):
    return str(uuid5(NAMESPACE_URL, f"bancocloud-demo:{kind}:{value}"))


def load_profiles(path):
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = book.active
        rows = sheet.values
        headers = next(rows)
        if len(set(headers)) != len(headers) or not set(KEEP).issubset(headers):
            raise ValueError("Workbook headers are missing or duplicated")
        positions = {h: i for i, h in enumerate(headers)}
        profiles = []
        for index, row in enumerate(rows, 2):
            if all(v is None for v in row):
                continue
            item = {k: row[positions[k]] for k in KEEP}
            if any(v is None for v in item.values()) or float(item["monto_promedio_transaccion"]) <= 0:
                raise ValueError(f"Invalid seed row {index}")
            item["customer_ref"] = identifier("customer", index)
            item["account_ref"] = identifier("account", index)
            item["monto_promedio_transaccion"] = round(float(item["monto_promedio_transaccion"]), 2)
            profiles.append(item)
        return profiles, headers
    finally:
        book.close()


def generate(profiles, count=10000, seed=42):
    rng = random.Random(seed)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(count):
        profile = profiles[i % len(profiles)]
        suspicious = i % 31 == 0
        amount = round(max(1.0, profile["monto_promedio_transaccion"] * rng.uniform(0.4, 2.1) * (20 if suspicious else 1)), 2)
        txid = identifier(f"tx-{seed}", i)
        time = base + timedelta(seconds=i * 60)
        transaction_type = TYPE.get(profile["tipo_operacion_frecuente"], "TRANSFER")
        event = {
            "schema_version": "1.0", "event_id": identifier(f"event-{seed}", i), "event_type": "TransactionPosted",
            "event_time": time.isoformat(), "transaction_id": txid, "customer_ref": profile["customer_ref"],
            "account_ref": profile["account_ref"], "transaction_type": transaction_type,
            "amount": amount, "currency": "PEN", "channel": "MOBILE" if profile["app_preferida"] != "Web Banking" else "WEB",
            "authentication_method": "TOKEN", "transaction_status": "POSTED",
            "device_ref": identifier("device-new" if suspicious else "device", i if suspicious else i % len(profiles)),
            "beneficiary_ref": identifier("beneficiary-new" if suspicious else "beneficiary", i if suspicious else i % len(profiles)),
            "location": {"country": "PE", "region": str(profile["departamento"])},
            "correlation_id": identifier(f"correlation-{seed}", i), "source_system": "synthetic-generator"
        }
        validate("transaction", event)
        label = {"transaction_id": txid, "is_fraud": int(suspicious),
                 "fraud_scenario": "new_device_beneficiary_amount" if suspicious else "none",
                 "label_timestamp": (time + timedelta(days=7)).isoformat(), "label_source": "synthetic_scenario"}
        yield event, label


def build(source, output=ROOT / "data/synthetic", count=10000, seed=42):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    profiles, headers = load_profiles(source)
    if not profiles:
        raise ValueError("No source rows")
    paths = [output / x for x in ("customer_seed.jsonl", "transaction_events.jsonl", "fraud_labels.jsonl")]
    import contextlib
    with contextlib.ExitStack() as stack:
        files = [stack.enter_context(p.open("w", encoding="utf-8")) for p in paths]
        for profile in profiles:
            files[0].write(json.dumps(profile, ensure_ascii=False) + "\n")
        labels = Counter()
        for event, label in generate(profiles, count, seed):
            files[1].write(json.dumps(event, ensure_ascii=False) + "\n")
            files[2].write(json.dumps(label, ensure_ascii=False) + "\n")
            labels[label["is_fraud"]] += 1
    audit = {"source_sha256": hashlib.sha256(Path(source).read_bytes()).hexdigest(), "source_rows": len(profiles),
             "generated_events": count, "seed": seed, "generated_label_counts": dict(labels),
             "profile_fields": list(KEEP) + ["customer_ref", "account_ref"],
             "excluded_source_fields": [h for h in EXCLUDE if h in headers],
             "source_has_no_primary_keys": True, "source_labels_are_not_ground_truth_for_generated_transactions": True}
    (ROOT / "data/quality").mkdir(exist_ok=True)
    (ROOT / "data/quality/source_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", default=str(ROOT / "data/synthetic"))
    parser.add_argument("--count", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.count, args.seed), indent=2))
