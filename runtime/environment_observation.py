"""Versioned, governed PR187 observations from the canonical MT5 feed."""

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Callable
from uuid import UUID, uuid5

from learning.execution_environment.policy import ENVIRONMENT_DIMENSIONS

DEFAULT_MARKET_STATE_PATH = Path(
    r"C:\Users\rp_fu\AppData\Roaming\MetaQuotes\Terminal\Common\Files\RP_AI_EA"
    r"\shared\XAUUSD\market_state.json"
)
OBSERVATION_POLICY_VERSION = "PR187-OBSERVATION-POLICY.1.0"
EXPECTED_SYMBOL = "XAUUSD"
EXPECTED_PRODUCER = "RP_AI_MT5_MARKET_STATE"
EXPECTED_PRODUCER_VERSION = "V1"
EXPECTED_SCHEMA_VERSION = "1.0"
EXPECTED_SOURCE_UUID = "dc3777c6-cf0d-5a7b-bd58-8a5c44568475"

_DIMENSIONS = (
    ("feed_stability", "read attempts", "fraction", "successful_reads / total_reads", ">= 0.95"),
    ("price_stream_continuity", "sequence_id", "fraction", "strictly_progressing_unique_sequences / sequence_transitions", ">= 0.99"),
    ("market_session_quality", "market_session_quality", "fraction", "minimum direct observation", ">= 0.8"),
    ("spread_quality", "spread_points", "points", "maximum direct observation", "<= 50"),
    ("latency_quality", "local monotonic read duration", "milliseconds", "maximum measured duration", "<= 250"),
    ("slippage_expectation", "slippage_expectation", "points", "maximum direct observation", "<= 30"),
    ("market_liquidity_quality", "market_liquidity_quality", "fraction", "minimum direct observation", ">= 0.8"),
    ("environment_consistency", "sequence_id, heartbeat_unix", "fraction", "strictly progressing pairs / transitions", ">= 0.8"),
    ("data_freshness", "heartbeat_unix", "seconds", "maximum(now - heartbeat_unix)", "0..5"),
    ("environment_completeness", "required policy source fields", "fraction", "complete_reads / total_reads", ">= 0.9"),
)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class EnvironmentObservationPolicy:
    """Immutable policy declaring every observation's semantics and provenance."""

    policy_version: str = OBSERVATION_POLICY_VERSION
    symbol: str = EXPECTED_SYMBOL
    producer: str = EXPECTED_PRODUCER
    producer_version: str = EXPECTED_PRODUCER_VERSION
    schema_version: str = EXPECTED_SCHEMA_VERSION
    source_uuid: str = EXPECTED_SOURCE_UUID
    heartbeat_field: str = "heartbeat_unix"
    sequence_field: str = "sequence_id"
    stale_limit_seconds: float = 5.0
    minimum_unique_observations: int = 3
    dimensions: tuple = _DIMENSIONS

    def __post_init__(self):
        if (
            self.policy_version != OBSERVATION_POLICY_VERSION
            or self.symbol != EXPECTED_SYMBOL
            or self.producer != EXPECTED_PRODUCER
            or self.producer_version != EXPECTED_PRODUCER_VERSION
            or self.schema_version != EXPECTED_SCHEMA_VERSION
            or self.source_uuid != EXPECTED_SOURCE_UUID
            or self.heartbeat_field != "heartbeat_unix"
            or self.sequence_field != "sequence_id"
            or type(self.stale_limit_seconds) is not float
            or self.stale_limit_seconds <= 0.0
            or type(self.minimum_unique_observations) is not int
            or self.minimum_unique_observations < 2
            or tuple(row[0] for row in self.dimensions) != ENVIRONMENT_DIMENSIONS
        ):
            raise ValueError("INVALID_ENVIRONMENT_OBSERVATION_POLICY")
        UUID(self.source_uuid)

    def payload(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @property
    def policy_digest(self):
        return hashlib.sha256(_canonical(self.payload()).encode()).hexdigest()

    @property
    def policy_uuid(self):
        return str(uuid5(UUID("ded7aebb-0861-5ea3-98c6-e2c3895b4880"), self.policy_digest))


class EnvironmentObservationError(ValueError):
    """Live observations could not be measured without inventing a value."""


@dataclass(frozen=True)
class GovernedEnvironmentObservation:
    observations: tuple[tuple[str, float], ...]
    captured_at: str
    observation_policy_uuid: str
    observation_policy_digest: str
    observation_policy_version: str
    source_provenance: tuple[tuple[str, str], ...]
    successful_reads: int
    malformed_reads: int
    unique_sequence_ids: tuple[int, ...]
    observation_duration_seconds: float


class GovernedEnvironmentObservationProducer:
    """Collect only identity-verified, unique, fresh telemetry observations."""

    def __init__(self, market_state_path: Path = DEFAULT_MARKET_STATE_PATH, *,
                 window_seconds: float = 5.0, sample_interval: float = 0.05,
                 policy: EnvironmentObservationPolicy | None = None,
                 clock: Callable[[], float] = time.time,
                 monotonic: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        if (not isinstance(market_state_path, Path) or type(window_seconds) is not float
                or type(sample_interval) is not float or window_seconds <= 0.0
                or sample_interval <= 0.0):
            raise EnvironmentObservationError("INVALID_OBSERVATION_CONFIGURATION")
        self.path, self.window_seconds, self.sample_interval = market_state_path, window_seconds, sample_interval
        self.policy = policy or EnvironmentObservationPolicy()
        self.clock, self.monotonic, self.sleep = clock, monotonic, sleep

    @staticmethod
    def _number(data, name):
        value = data.get(name)
        if type(value) not in (int, float) or not isfinite(value):
            raise EnvironmentObservationError("MARKET_STATE_TELEMETRY_INCOMPLETE")
        return float(value)

    def _validate_identity(self, data):
        expected = {"symbol": self.policy.symbol, "producer": self.policy.producer,
                    "producer_version": self.policy.producer_version,
                    "schema_version": self.policy.schema_version,
                    "source_uuid": self.policy.source_uuid}
        if any(data.get(name) != value for name, value in expected.items()):
            raise EnvironmentObservationError("MARKET_STATE_SOURCE_IDENTITY_MISMATCH")

    def collect(self):
        started_wall, started = self.clock(), self.monotonic()
        attempts = successful = malformed = complete = 0
        unique, samples, latencies = {}, [], []
        while True:
            attempts += 1
            read_started = self.monotonic()
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self._validate_identity(data)
                now = self.clock()
                heartbeat = self._number(data, self.policy.heartbeat_field)
                age = now - heartbeat
                if age < 0.0:
                    raise EnvironmentObservationError("MARKET_STATE_HEARTBEAT_FUTURE")
                if age > self.policy.stale_limit_seconds:
                    raise EnvironmentObservationError("MARKET_STATE_HEARTBEAT_STALE")
                sequence_value = self._number(data, self.policy.sequence_field)
                if not sequence_value.is_integer() or sequence_value < 0.0:
                    raise EnvironmentObservationError("INVALID_MARKET_STATE_SEQUENCE")
                sequence = int(sequence_value)
                direct = {name: self._number(data, name) for name in (
                    "bid", "spread_points", "market_session_quality",
                    "slippage_expectation", "market_liquidity_quality")}
                if (direct["bid"] <= 0.0 or direct["spread_points"] < 0.0
                        or direct["slippage_expectation"] < 0.0
                        or not 0.0 <= direct["market_session_quality"] <= 1.0
                        or not 0.0 <= direct["market_liquidity_quality"] <= 1.0):
                    raise EnvironmentObservationError("INVALID_MARKET_STATE_TELEMETRY")
                successful += 1
                complete += 1
                latency = max(0.0, self.monotonic() - read_started) * 1000.0
                if sequence not in unique:
                    unique[sequence] = heartbeat
                    samples.append((sequence, heartbeat, age, direct))
                    latencies.append(latency)
                elif unique[sequence] != heartbeat:
                    raise EnvironmentObservationError("MARKET_STATE_IDENTITY_CONFLICT")
            except EnvironmentObservationError as exc:
                if str(exc) in {"MARKET_STATE_HEARTBEAT_FUTURE", "MARKET_STATE_HEARTBEAT_STALE",
                                "MARKET_STATE_SOURCE_IDENTITY_MISMATCH", "MARKET_STATE_IDENTITY_CONFLICT"}:
                    raise
                malformed += 1
            except (OSError, json.JSONDecodeError, UnicodeError):
                malformed += 1
            if self.monotonic() - started >= self.window_seconds:
                break
            self.sleep(min(self.sample_interval, self.window_seconds - (self.monotonic() - started)))

        duration = self.monotonic() - started
        if len(samples) < self.policy.minimum_unique_observations:
            raise EnvironmentObservationError("INSUFFICIENT_UNIQUE_ENVIRONMENT_OBSERVATIONS")
        transitions = len(samples) - 1
        progressing = sum(b[0] > a[0] for a, b in zip(samples, samples[1:]))
        consistent = sum(b[0] > a[0] and b[1] > a[1] for a, b in zip(samples, samples[1:]))
        if progressing != transitions:
            raise EnvironmentObservationError("MARKET_STATE_SEQUENCE_NOT_PROGRESSING")
        observations = {
            "feed_stability": successful / attempts,
            "price_stream_continuity": progressing / transitions,
            "market_session_quality": min(x[3]["market_session_quality"] for x in samples),
            "spread_quality": max(x[3]["spread_points"] for x in samples),
            "latency_quality": max(latencies),
            "slippage_expectation": max(x[3]["slippage_expectation"] for x in samples),
            "market_liquidity_quality": min(x[3]["market_liquidity_quality"] for x in samples),
            "environment_consistency": consistent / transitions,
            "data_freshness": max(x[2] for x in samples),
            "environment_completeness": complete / attempts,
        }
        captured_at = datetime.fromtimestamp(self.clock(), timezone.utc).isoformat().replace("+00:00", "Z")
        provenance = (("path", str(self.path)), ("source_uuid", self.policy.source_uuid),
                      ("producer", self.policy.producer), ("producer_version", self.policy.producer_version),
                      ("schema_version", self.policy.schema_version),
                      ("heartbeat_field", self.policy.heartbeat_field), ("sequence_field", self.policy.sequence_field))
        return GovernedEnvironmentObservation(
            tuple((name, float(observations[name])) for name in ENVIRONMENT_DIMENSIONS), captured_at,
            self.policy.policy_uuid, self.policy.policy_digest, self.policy.policy_version,
            provenance, successful, malformed, tuple(unique), float(duration))
