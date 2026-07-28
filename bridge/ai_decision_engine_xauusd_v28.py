#!/usr/bin/env python3
"""Executable V28 PR-A loop: validated market state to atomic HOLD decision."""
from __future__ import annotations
import argparse
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Callable

# Support both ``python -m bridge...`` and direct script startup.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridge.v28.decision_contract import build_decision
from bridge.v28.market_normalizer import normalize_market_state
from bridge.v28.market_reader import MarketReader, MarketStateError
from bridge.v28.publisher import AtomicDecisionPublisher
from bridge.v28.runtime_context import construct_runtime_context
from bridge.v28.runtime_health import RuntimeHealth

RUNTIME_VERSION = "V28.PR-A"
DEFAULT_ROOT = Path(os.environ.get("RP_AI_SHARED_ROOT", r"D:\RP_AI_EA\shared\XAUUSD"))
DEFAULT_MARKET_PATH = DEFAULT_ROOT / "market_state.json"
DEFAULT_DECISION_PATH = DEFAULT_ROOT / "decision.json"
LOGGER = logging.getLogger("v28_decision_engine")


class V28DecisionEngine:
    def __init__(self, market_path: str | Path, decision_path: str | Path, *,
                 max_age_seconds: float = 5.0, clock: Callable[[], float] = time.time) -> None:
        self.clock = clock
        self.reader = MarketReader(market_path, max_age_seconds=max_age_seconds, clock=clock)
        self.publisher = AtomicDecisionPublisher(decision_path)
        self.health = RuntimeHealth(runtime_version=RUNTIME_VERSION)

    def cycle(self) -> dict[str, object] | None:
        try:
            market = self.reader.read()
            self.health.schema_state = "VALID"
            self.health.freshness_state = "FRESH"
            now = self.clock()
            normalized = normalize_market_state(market)
            context = construct_runtime_context(normalized, now=now)
            self.health.heartbeat_age = context.heartbeat_age_seconds
            decision = build_decision(context, now=now)
            self.publisher.publish(decision)
            self.health.last_publish_timestamp = str(decision["published_at"])
            self.health.startup_state = "RUNNING"
            LOGGER.info("decision_published %s", json.dumps({
                "action": "HOLD", "sequence_id": decision["sequence_id"],
                "health": self.health.snapshot()}, sort_keys=True))
            return decision
        except MarketStateError as error:
            self.health.startup_state = "WAITING_FOR_VALID_MARKET"
            self.health.schema_state = "INVALID" if error.code.startswith("SCHEMA") or "MALFORMED" in error.code else "UNKNOWN"
            self.health.freshness_state = "STALE" if error.code == "MARKET_STATE_STALE" else "UNKNOWN"
            LOGGER.warning("market_rejected code=%s health=%s", error.code, json.dumps(self.health.snapshot(), sort_keys=True))
            return None

    def run(self, *, interval_seconds: float = 1.0, iterations: int | None = None) -> None:
        LOGGER.info("runtime_started health=%s", json.dumps(self.health.snapshot(), sort_keys=True))
        completed = 0
        while iterations is None or completed < iterations:
            self.cycle()
            completed += 1
            if iterations is None or completed < iterations:
                time.sleep(interval_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", type=Path, default=DEFAULT_MARKET_PATH)
    parser.add_argument("--decision", type=Path, default=DEFAULT_DECISION_PATH)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--max-age", type=float, default=5.0)
    parser.add_argument("--iterations", type=int, help="bounded replay/test cycles")
    args = parser.parse_args()
    if args.interval < 0 or args.iterations is not None and args.iterations < 1:
        parser.error("interval must be non-negative and iterations must be positive")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    V28DecisionEngine(args.market, args.decision, max_age_seconds=args.max_age).run(
        interval_seconds=args.interval, iterations=args.iterations)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
