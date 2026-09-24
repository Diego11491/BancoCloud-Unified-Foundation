"""At-least-once publisher: acknowledge only after the consumer responds successfully."""
import time
from urllib.error import HTTPError, URLError

from .adapters import local_event_sink
from .db import connect


def publish_once(client=None):
    with connect() as conn:
        with conn.transaction():
            row = conn.execute("SELECT event_id,payload FROM outbox_events WHERE published_at IS NULL ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
            if not row:
                return False
            event_id, event = row
            # The lock is held during delivery. On timeout the event stays pending and is replayed.
            local_event_sink(client).publish(event)
            conn.execute("UPDATE outbox_events SET published_at=now(),attempts=attempts+1 WHERE event_id=%s", (event_id,))
            return True


if __name__ == "__main__":
    while True:
        try:
            if not publish_once():
                time.sleep(1)
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            print(f"publisher retry: {type(exc).__name__}", flush=True)
            time.sleep(3)
