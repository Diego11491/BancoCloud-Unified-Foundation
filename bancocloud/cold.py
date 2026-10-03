"""LOCAL FIRST cold path projection; swap storage adapter for ADLS in Student LITE."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from .contracts import validate


def project(events_path, out_dir):
    out = Path(out_dir)
    for level in ("bronze", "silver", "gold", "quarantine"):
        (out / level).mkdir(parents=True, exist_ok=True)
    seen = set()
    totals = defaultdict(lambda: {"transaction_count":0,"amount_pen":0.0})
    counts = {"bronze":0,"silver":0,"quarantine":0,"duplicate":0}
    with Path(events_path).open(encoding="utf-8") as source, (out / "bronze/events.jsonl").open("w", encoding="utf-8") as bronze, (out / "silver/events.jsonl").open("w", encoding="utf-8") as silver, (out / "quarantine/rejected.jsonl").open("w", encoding="utf-8") as bad:
        for line_no, line in enumerate(source, 1):
            counts["bronze"] += 1
            bronze.write(line)
            try:
                event = validate("transaction", json.loads(line))
                if event["event_id"] in seen:
                    counts["duplicate"] += 1
                    continue
                seen.add(event["event_id"])
                silver.write(json.dumps(event,ensure_ascii=False)+"\n")
                counts["silver"] += 1
                key = (event["event_time"][:10],event["channel"])
                totals[key]["transaction_count"] += 1
                totals[key]["amount_pen"] += event["amount"]
            except Exception:
                counts["quarantine"] += 1
                bad.write(json.dumps({"line":line_no,"reason":"invalid_event"})+"\n")
    with (out / "gold/transactions_by_day_channel.jsonl").open("w", encoding="utf-8") as target:
        for (day,channel), value in sorted(totals.items()):
            target.write(json.dumps({"day":day,"channel":channel,"transaction_count":value["transaction_count"],"amount_pen":round(value["amount_pen"],2)})+"\n")
    assert counts["bronze"] == counts["silver"]+counts["quarantine"]+counts["duplicate"]
    (out / "reconciliation.json").write_text(json.dumps(counts,indent=2), encoding="utf-8")
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("events")
    parser.add_argument("output")
    args = parser.parse_args()
    print(project(args.events,args.output))
