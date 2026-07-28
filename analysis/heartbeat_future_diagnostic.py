"""Capture wall-clock evidence for market-state heartbeat investigations.

This utility is deliberately observational.  It neither imports nor invokes the
Runtime collector and never changes the market-state publication.
"""

import argparse
import json
import time
from pathlib import Path


def capture(path: Path, *, count: int, interval_seconds: float) -> list[dict]:
    """Return ordered snapshots with the clock bounds surrounding each read."""
    observations = []
    for index in range(count):
        local_time_before = time.time()
        document = json.loads(path.read_text(encoding="utf-8"))
        local_time_after = time.time()
        heartbeat = document["heartbeat_unix"]
        if type(heartbeat) not in (int, float):
            raise ValueError("HEARTBEAT_NOT_NUMERIC")
        local_time = (local_time_before + local_time_after) / 2.0
        observations.append(
            {
                "sample": index + 1,
                "sequence_id": document.get("sequence_id"),
                "heartbeat_unix": heartbeat,
                "local_time": local_time,
                "delta_seconds": heartbeat - local_time,
                "local_time_before_read": local_time_before,
                "local_time_after_read": local_time_after,
                "read_uncertainty_seconds": local_time_after - local_time_before,
            }
        )
        if index + 1 < count:
            time.sleep(interval_seconds)
    return observations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--interval-seconds", type=float, default=0.25)
    arguments = parser.parse_args()
    if arguments.count < 2 or arguments.interval_seconds < 0.0:
        parser.error("count must be at least 2 and interval must be non-negative")
    for observation in capture(
        arguments.path,
        count=arguments.count,
        interval_seconds=arguments.interval_seconds,
    ):
        print(json.dumps(observation, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
