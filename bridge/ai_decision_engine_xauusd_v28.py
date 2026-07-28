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

from bridge.v28.decision_contract import build_decision, validate_pr_a_decision
from bridge.v28.market_normalizer import normalize_market_state
from bridge.v28.market_reader import MarketReader, MarketStateError
from bridge.v28.publisher import AtomicDecisionPublisher, DecisionPathOwnership, OwnershipError, PublicationError
from bridge.v28.runtime_context import construct_runtime_context
from bridge.v28.runtime_health import RuntimeHealth

RUNTIME_VERSION = "V28.PR-A"
DEFAULT_ROOT = Path(os.environ.get("RP_AI_SHARED_ROOT", r"D:\RP_AI_EA\shared\XAUUSD"))
DEFAULT_MARKET_PATH = DEFAULT_ROOT / "market_state.json"
DEFAULT_DECISION_PATH = DEFAULT_ROOT / "decision.json"
LOGGER = logging.getLogger("v28_decision_engine")


class V28DecisionEngine:
    def __init__(self, market_path: str | Path, decision_path: str | Path, *,
                 expected_symbol: str = "XAUUSD", expected_timeframe: str | None = None,
                 max_age_seconds: float = 5.0, clock: Callable[[], float] = time.time,
                 reset_sequence: bool = False) -> None:
        self.clock = clock
        self.reader = MarketReader(market_path, expected_symbol=expected_symbol,
                                   expected_timeframe=expected_timeframe, max_age_seconds=max_age_seconds)
        self.publisher = AtomicDecisionPublisher(decision_path)
        self.ownership = DecisionPathOwnership(decision_path)
        self.health = RuntimeHealth(runtime_version=RUNTIME_VERSION)
        self.last_published_sequence: int | None = None
        self.reset_sequence = reset_sequence

    def activate(self) -> None:
        self.ownership.acquire()
        try:
            self.publisher.cleanup_stale_temporary()
            if self.reset_sequence:
                try:
                    self.publisher.path.unlink()
                except FileNotFoundError:
                    pass
                LOGGER.warning("governed_sequence_reset path=%s", self.publisher.path)
                return
            if self.publisher.path.exists():
                try:
                    existing = json.loads(self.publisher.path.read_text(encoding="utf-8"))
                    validate_pr_a_decision(existing)
                    self.last_published_sequence = existing["sequence_id"]
                except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError, KeyError) as error:
                    raise RuntimeError("EXISTING_DECISION_SEQUENCE_UNRECOVERABLE") from error
        except Exception:
            self.ownership.release()
            raise

    def cycle(self) -> dict[str, object] | None:
        self.health.begin_cycle()
        now = self.clock()  # the sole authoritative clock snapshot for this cycle
        try:
            market = self.reader.read(now=now)
            self.health.schema_state = "VALID"
            self.health.freshness_state = "FRESH"
            sequence = market["sequence_id"]
            normalized = normalize_market_state(market)
            context = construct_runtime_context(normalized, now=now)
            self.health.heartbeat_age = context.heartbeat_age_seconds
            if self.last_published_sequence is not None:
                if sequence == self.last_published_sequence:
                    self.health.startup_state = "RUNNING"
                    self.health.cycle_state = "DUPLICATE_SUPPRESSED"
                    return None
                if sequence < self.last_published_sequence:
                    raise MarketStateError("SEQUENCE_REGRESSION")
            decision = build_decision(context, now=now)
            self.publisher.publish(decision)
            self.last_published_sequence = sequence
            self.health.last_publish_timestamp = str(decision["published_at"])
            self.health.startup_state = "RUNNING"
            self.health.cycle_state = "PUBLISHED"
            LOGGER.info("decision_published %s", json.dumps({"action": "HOLD", "sequence_id": sequence,
                        "health": self.health.snapshot()}, sort_keys=True))
            return decision
        except MarketStateError as error:
            schema = "INVALID" if error.code.startswith(("SCHEMA", "INCOMPATIBLE", "SYMBOL", "TIMEFRAME")) else "UNKNOWN"
            freshness = "STALE" if error.code == "MARKET_STATE_STALE" else "UNKNOWN"
            self.health.fail(error.code, schema=schema, freshness=freshness)
        except PublicationError as error:
            self.health.fail(str(error), schema="VALID", freshness="FRESH")
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            self.health.fail("PIPELINE_CONSTRUCTION_FAILED", schema="VALID", freshness="FRESH")
            LOGGER.exception("pipeline_construction_failed error=%s", error)
        except OSError as error:
            self.health.fail("RUNTIME_IO_FAILED", schema="VALID", freshness="FRESH")
            LOGGER.exception("runtime_io_failed error=%s", error)
        LOGGER.warning("cycle_failed health=%s", json.dumps(self.health.snapshot(), sort_keys=True))
        return None

    def run(self, *, interval_seconds: float = 1.0, iterations: int | None = None) -> None:
        self.activate()
        LOGGER.info("runtime_started health=%s", json.dumps(self.health.snapshot(), sort_keys=True))
        try:
            completed = 0
            while iterations is None or completed < iterations:
                self.cycle()
                completed += 1
                if iterations is None or completed < iterations:
                    time.sleep(interval_seconds)
        finally:
            self.ownership.release()

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", type=Path, default=DEFAULT_MARKET_PATH)
    parser.add_argument("--decision", type=Path, default=DEFAULT_DECISION_PATH)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--max-age", type=float, default=5.0)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--timeframe")
    parser.add_argument("--reset-sequence", action="store_true", help="explicitly start a new governed sequence lifecycle")
    parser.add_argument("--iterations", type=int, help="bounded replay/test cycles")
    args = parser.parse_args()
    if args.interval < 0 or args.iterations is not None and args.iterations < 1:
        parser.error("interval must be non-negative and iterations must be positive")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        V28DecisionEngine(args.market, args.decision, expected_symbol=args.symbol,
                          expected_timeframe=args.timeframe, max_age_seconds=args.max_age,
                          reset_sequence=args.reset_sequence).run(
            interval_seconds=args.interval, iterations=args.iterations)
    except (ValueError, RuntimeError, OwnershipError, PublicationError, OSError) as error:
        LOGGER.critical("fatal_startup code=%s", error)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
