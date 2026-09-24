"""Send exactly the synthetic fixture to the LOCAL FIRST fraud consumer."""
import argparse
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError

from .contracts import validate
from .adapters import local_event_sink


def replay(path: Path, expected: int, client=None, progress=500, pause=time.sleep):
    if os.environ.get("EVENT_SINK", "local-http") != "local-http":
        raise RuntimeError("Cloud event sinks are disabled")
    if expected <= 0:
        raise ValueError("Expected event count must be positive")
    path = Path(path)
    with path.open(encoding="utf-8") as source:
        lines = sum(bool(line.strip()) for line in source)
    if lines != expected:
        raise ValueError(f"Fixture line count {lines} differs from expected {expected}")
    if not os.environ.get("DEMO_API_KEY"):
        raise RuntimeError("DEMO_API_KEY missing")
    sink = local_event_sink(client)
    result = {"fixture_lines":lines,"accepted":0,"replayed":0,"failed":0}
    with path.open(encoding="utf-8") as source:
        for index, line in enumerate(source,1):
            event = validate("transaction",json.loads(line))
            if event.get("source_system") != "synthetic-generator":
                raise ValueError(f"Unexpected source_system on line {index}")
            for attempt in range(4):
                try:
                    data = sink.publish(event)
                    if data.get("score",{}).get("correlation_id") != event["correlation_id"]:
                        raise ValueError(f"Correlation ID mismatch on line {index}")
                    result["replayed" if data.get("replay") else "accepted"] += 1
                    break
                except (HTTPError, URLError, OSError, TimeoutError) as exc:
                    retryable = (not isinstance(exc, HTTPError) and isinstance(exc,(URLError,OSError,TimeoutError))) or (isinstance(exc,HTTPError) and exc.code >= 500)
                    if not retryable or attempt == 3:
                        result["failed"] += 1
                        raise RuntimeError(f"Fixture delivery failed at line {index}: {type(exc).__name__}") from exc
                    pause(2**attempt)
            if progress and index % progress == 0:
                print(json.dumps({"processed":index,"accepted":result["accepted"],"replayed":result["replayed"]}),flush=True)
    if result["accepted"]+result["replayed"] != expected:
        raise RuntimeError("Incomplete replay")
    print(json.dumps(result),flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("events",type=Path)
    parser.add_argument("--expected",type=int,required=True)
    args = parser.parse_args()
    replay(args.events,args.expected)
