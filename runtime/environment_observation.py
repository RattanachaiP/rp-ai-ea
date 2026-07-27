"""Governed producer of PR187 observations from the live MT5 market-state feed."""

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Callable

from learning.execution_environment.policy import ENVIRONMENT_DIMENSIONS


DEFAULT_MARKET_STATE_PATH = Path(
    r"C:\Users\rp_fu\AppData\Roaming\MetaQuotes\Terminal\Common\Files\RP_AI_EA"
    r"\shared\XAUUSD\market_state.json"
)


class EnvironmentObservationError(ValueError):
    """Live observations could not be measured without inventing a value."""


@dataclass(frozen=True)
class GovernedEnvironmentObservation:
    observations: tuple[tuple[str, float], ...]
    captured_at: str


class GovernedEnvironmentObservationProducer:
    """Measure the environment; missing telemetry always fails closed.

    The producer deliberately uses only values observed at the Runtime's canonical
    market-state boundary.  Ratios describe the sampling window, read latency is
    measured locally, freshness comes from file metadata, and the executable-price
    uncertainty (half the measured bid/ask spread) is the slippage expectation.
    """

    def __init__(
        self,
        market_state_path: Path = DEFAULT_MARKET_STATE_PATH,
        *,
        window_seconds: float = 5.0,
        sample_interval: float = 0.05,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if (
            not isinstance(market_state_path, Path)
            or type(window_seconds) is not float
            or type(sample_interval) is not float
            or window_seconds <= 0.0
            or sample_interval <= 0.0
        ):
            raise EnvironmentObservationError("INVALID_OBSERVATION_CONFIGURATION")
        self.path = market_state_path
        self.window_seconds = window_seconds
        self.sample_interval = sample_interval
        self.clock = clock
        self.sleep = sleep

    @staticmethod
    def _number(data, name):
        value = data.get(name)
        if type(value) not in (int, float) or not isfinite(value):
            raise EnvironmentObservationError("MARKET_STATE_TELEMETRY_INCOMPLETE")
        return float(value)

    def collect(self):
        started = self.clock()
        deadline = started + self.window_seconds
        attempts = successes = complete = valid_quotes = continuous = consistent = 0
        spreads, latencies, freshness = [], [], []
        previous_sequence = None

        while True:
            attempts += 1
            read_started = self.clock()
            try:
                stat = self.path.stat()
                data = json.loads(self.path.read_text(encoding="utf-8"))
                bid = self._number(data, "bid")
                spread = self._number(data, "spread_points")
                sequence = self._number(data, "sequence_id")
                if bid <= 0.0 or spread < 0.0 or sequence < 0.0:
                    raise EnvironmentObservationError("INVALID_MARKET_STATE_TELEMETRY")
                successes += 1
                complete += 1
                valid_quotes += 1
                spreads.append(spread)
                latencies.append(max(0.0, self.clock() - read_started) * 1000.0)
                freshness.append(max(0.0, self.clock() - stat.st_mtime))
                if previous_sequence is None or sequence >= previous_sequence:
                    continuous += 1
                    consistent += 1
                previous_sequence = sequence
            except (OSError, json.JSONDecodeError, EnvironmentObservationError):
                pass
            now = self.clock()
            if now >= deadline:
                break
            self.sleep(min(self.sample_interval, deadline - now))

        if attempts < 2 or not spreads or complete != attempts:
            raise EnvironmentObservationError("ENVIRONMENT_OBSERVATION_INCOMPLETE")
        observations = {
            "feed_stability": successes / attempts,
            "price_stream_continuity": continuous / attempts,
            "market_session_quality": valid_quotes / attempts,
            "spread_quality": max(spreads),
            "latency_quality": max(latencies),
            "slippage_expectation": max(spreads) / 2.0,
            "market_liquidity_quality": sum(value <= 50.0 for value in spreads) / attempts,
            "environment_consistency": consistent / attempts,
            "data_freshness": max(freshness),
            "environment_completeness": complete / attempts,
        }
        captured_at = datetime.fromtimestamp(self.clock(), timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
        return GovernedEnvironmentObservation(
            tuple((name, float(observations[name])) for name in ENVIRONMENT_DIMENSIONS),
            captured_at,
        )
