"""PR206 passive discovery of reproducible operational patterns.

This module deliberately accepts public, immutable post-trade contracts only.
It has no dependency on Runtime, Strategy, governance, or broker components.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
from statistics import fmean, median
from typing import Iterable
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from operational_evidence.outcome_attribution import (
    OutcomeAttribution, OutcomeAttributionEngine, OutcomeAttributionError,
)
from runtime.completed_trade_event import CompletedTradeEvent
from runtime.live_outcome_capture import LiveOutcomeRecord


PATTERN_VERSION = "PR206-PATTERN.1"


class PatternDiscoveryError(ValueError):
    """A fail-closed source, discovery, or persistence failure."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise PatternDiscoveryError("PATTERN_SERIALIZATION_FAILURE") from exc


def _uuid(value: object) -> bool:
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


@dataclass(frozen=True, slots=True)
class PatternDiscoveryConfig:
    minimum_sample_count: int = 10
    confidence_level: float = 0.95

    def __post_init__(self) -> None:
        if (not isinstance(self.minimum_sample_count, int)
                or isinstance(self.minimum_sample_count, bool)
                or self.minimum_sample_count < 2):
            raise PatternDiscoveryError("INVALID_SAMPLE_THRESHOLD")
        if (not isinstance(self.confidence_level, (int, float))
                or isinstance(self.confidence_level, bool)
                or not 0.5 < self.confidence_level < 1):
            raise PatternDiscoveryError("INVALID_CONFIDENCE_LEVEL")


@dataclass(frozen=True, slots=True)
class ObservationWindow:
    started_at: str
    ended_at: str

    def to_dict(self) -> dict[str, str]:
        return {"started_at": self.started_at, "ended_at": self.ended_at}


@dataclass(frozen=True, slots=True)
class Pattern:
    pattern_uuid: str
    pattern_type: str
    source_attribution_uuids: tuple[str, ...]
    sample_count: int
    configured_confidence_level: float
    observation_window: ObservationWindow
    supporting_evidence: tuple[tuple[str, object], ...]
    discovery_timestamp: str
    replay_identity: str
    sha256_digest: str
    contract_version: str = PATTERN_VERSION
    passive_observation_only: bool = True

    def __post_init__(self) -> None:
        if self.contract_version != PATTERN_VERSION or not self.passive_observation_only:
            raise PatternDiscoveryError("INVALID_PATTERN_CONTRACT")
        if not _uuid(self.pattern_uuid) or not _uuid(self.replay_identity):
            raise PatternDiscoveryError("INVALID_PATTERN_UUID")
        if (not self.source_attribution_uuids
                or tuple(sorted(set(self.source_attribution_uuids))) != self.source_attribution_uuids
                or not all(_uuid(value) for value in self.source_attribution_uuids)
                or self.sample_count != len(self.source_attribution_uuids)):
            raise PatternDiscoveryError("INVALID_PATTERN_SOURCES")
        if not 0.5 < self.configured_confidence_level < 1:
            raise PatternDiscoveryError("INVALID_CONFIGURED_CONFIDENCE_LEVEL")
        if not self.pattern_type or not isinstance(self.supporting_evidence, tuple):
            raise PatternDiscoveryError("INVALID_SUPPORTING_EVIDENCE")
        if tuple(key for key, _ in self.supporting_evidence) != tuple(sorted(key for key, _ in self.supporting_evidence)):
            raise PatternDiscoveryError("INVALID_SUPPORTING_EVIDENCE")
        expected = str(uuid5(NAMESPACE_URL, "pr206-pattern:" + sha256(
            _canonical(self._identity_body())).hexdigest()))
        if self.pattern_uuid != expected:
            raise PatternDiscoveryError("PATTERN_UUID_MISMATCH")
        if self.sha256_digest != sha256(_canonical(self._body())).hexdigest():
            raise PatternDiscoveryError("PATTERN_DIGEST_MISMATCH")

    def _identity_body(self) -> dict[str, object]:
        return {
            "pattern_type": self.pattern_type,
            "source_attribution_uuids": list(self.source_attribution_uuids),
            "sample_count": self.sample_count,
            "configured_confidence_level": self.configured_confidence_level,
            "observation_window": self.observation_window.to_dict(),
            "supporting_evidence": dict(self.supporting_evidence),
            "discovery_timestamp": self.discovery_timestamp,
            "replay_identity": self.replay_identity,
            "contract_version": self.contract_version,
            "passive_observation_only": self.passive_observation_only,
        }

    def _body(self) -> dict[str, object]:
        return {"pattern_uuid": self.pattern_uuid, **self._identity_body()}

    def to_dict(self) -> dict[str, object]:
        return {**self._body(), "sha256_digest": self.sha256_digest}

    @classmethod
    def create(cls, pattern_type: str, rows: list[tuple[OutcomeAttribution,
                     CompletedTradeEvent, LiveOutcomeRecord]],
               configured_confidence_level: float,
               evidence: dict[str, object]) -> "Pattern":
        sources = tuple(sorted(row[0].attribution_uuid for row in rows))
        starts = [row[1].open_time for row in rows]
        ends = [row[1].close_time for row in rows]
        timestamps = [row[0].timestamp for row in rows]
        replays = {row[0].replay_identity for row in rows}
        # A discovery batch represents one replay. Mixed replay evidence is not repairable.
        if len(replays) != 1:
            raise PatternDiscoveryError("REPLAY_IDENTITY_INCONSISTENT")
        values = dict(
            pattern_type=pattern_type, source_attribution_uuids=sources,
            sample_count=len(rows),
            configured_confidence_level=configured_confidence_level,
            observation_window=ObservationWindow(min(starts), max(ends)),
            supporting_evidence=tuple(sorted(evidence.items())),
            discovery_timestamp=max(timestamps), replay_identity=next(iter(replays)),
            contract_version=PATTERN_VERSION, passive_observation_only=True,
        )
        identity = str(uuid5(NAMESPACE_URL, "pr206-pattern:" + sha256(
            _canonical({**values, "observation_window": values["observation_window"].to_dict(),
                        "supporting_evidence": dict(values["supporting_evidence"]),
                        "source_attribution_uuids": list(sources)})).hexdigest()))
        body = {"pattern_uuid": identity, **values,
                "observation_window": values["observation_window"].to_dict(),
                "supporting_evidence": dict(values["supporting_evidence"]),
                "source_attribution_uuids": list(sources)}
        return cls(pattern_uuid=identity, sha256_digest=sha256(_canonical(body)).hexdigest(), **values)


def _summary(values: Iterable[float]) -> dict[str, float]:
    ordered = sorted(float(value) for value in values)
    return {"minimum": ordered[0], "maximum": ordered[-1],
            "mean": fmean(ordered), "median": median(ordered)}


class PatternDiscoveryEngine:
    """Describe recurring post-trade behaviour without scoring or advice."""

    def __init__(self, config: PatternDiscoveryConfig | None = None) -> None:
        self.config = config or PatternDiscoveryConfig()

    def discover(self, attributions: Iterable[OutcomeAttribution],
                 completed_events: Iterable[CompletedTradeEvent],
                 live_outcomes: Iterable[LiveOutcomeRecord]) -> tuple[Pattern, ...]:
        attrs, events, outcomes = tuple(attributions), tuple(completed_events), tuple(live_outcomes)
        if len(attrs) < self.config.minimum_sample_count:
            raise PatternDiscoveryError("INSUFFICIENT_SAMPLE_SIZE")
        if len({item.attribution_uuid for item in attrs}) != len(attrs):
            raise PatternDiscoveryError("DUPLICATE_SOURCE_ATTRIBUTION")
        by_event = {item.event_uuid: item for item in events}
        by_outcome = {item.record_uuid: item for item in outcomes}
        if len(by_event) != len(events) or len(by_outcome) != len(outcomes):
            raise PatternDiscoveryError("DUPLICATE_SOURCE_EVIDENCE")
        rows = []
        for attribution in attrs:
            try:
                event = by_event[attribution.parent_completed_trade_event_uuid]
                outcome = by_outcome[attribution.source_live_outcome_record_uuid]
                verified = OutcomeAttributionEngine().attribute(event, outcome)
            except (KeyError, OutcomeAttributionError, ValueError, TypeError) as exc:
                raise PatternDiscoveryError("SOURCE_ATTRIBUTION_INTEGRITY_FAILURE") from exc
            if verified != attribution:
                raise PatternDiscoveryError("SOURCE_ATTRIBUTION_INTEGRITY_FAILURE")
            rows.append((attribution, event, outcome))
        if len({row[0].replay_identity for row in rows}) != 1:
            raise PatternDiscoveryError("REPLAY_IDENTITY_INCONSISTENT")

        configured_confidence_level = float(self.config.confidence_level)
        patterns: list[Pattern] = []
        def add(kind: str, selected: list, evidence: dict[str, object]) -> None:
            if len(selected) >= self.config.minimum_sample_count:
                patterns.append(Pattern.create(
                    kind, selected, configured_confidence_level, evidence))

        winners = [row for row in rows if row[0].classification == "PROFITABLE"]
        losers = [row for row in rows if row[0].classification == "LOSS"]
        add("WINNING_TRADE_CHARACTERISTICS", winners, {
            "directions": sorted({row[1].direction for row in winners}),
            "net_profit": _summary(row[1].net_profit for row in winners) if winners else {},
        })
        add("LOSING_TRADE_CHARACTERISTICS", losers, {
            "directions": sorted({row[1].direction for row in losers}),
            "net_profit": _summary(row[1].net_profit for row in losers) if losers else {},
        })
        add("ENTRY_TIMING_CLUSTER", rows, {"utc_hour_counts": self._hours(row[1].open_time for row in rows)})
        add("EXIT_TIMING_CLUSTER", rows, {"utc_hour_counts": self._hours(row[1].close_time for row in rows)})
        add("STOP_LOSS_DISTRIBUTION", rows, {"configured_stop_loss": _summary(row[1].stop_loss for row in rows)})
        add("TAKE_PROFIT_DISTRIBUTION", rows, {"configured_take_profit": _summary(row[1].take_profit for row in rows)})
        add("TRADE_DURATION_DISTRIBUTION", rows, {"seconds": _summary(row[2].trade_duration_seconds for row in rows)})
        add("LATENCY_DISTRIBUTION", rows, {"seconds": _summary(row[2].execution_latency_seconds for row in rows)})
        manual = sum("MANUAL" in row[1].exit_reason.upper() for row in rows)
        add("MANUAL_INTERVENTION_FREQUENCY", rows, {"manual_count": manual, "frequency": manual / len(rows)})
        add("REPLAY_CONSISTENCY", rows, {"consistent": True, "verified_count": len(rows)})
        if len({item.pattern_uuid for item in patterns}) != len(patterns):
            raise PatternDiscoveryError("DUPLICATE_PATTERN_IDENTITY")
        return tuple(sorted(patterns, key=lambda item: item.pattern_type))

    @staticmethod
    def _hours(values: Iterable[str]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for value in values:
            hour = f"{datetime.fromisoformat(value.replace('Z', '+00:00')).hour:02d}"
            counts[hour] = counts.get(hour, 0) + 1
        return dict(sorted(counts.items()))


class PatternRepository:
    """Atomic append-only repository; an existing identity is always rejected."""

    def __init__(self, root: str | Path = "operational_evidence") -> None:
        self.root = Path(root)

    def append(self, pattern: Pattern) -> Path:
        if type(pattern) is not Pattern:
            raise TypeError("PATTERN_REQUIRED")
        # Revalidation detects mutation before touching storage.
        pattern.__post_init__()
        directory = self.root / "patterns"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"pattern_{pattern.pattern_uuid}.json"
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(_canonical(pattern.to_dict()) + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise PatternDiscoveryError("DUPLICATE_PATTERN_IDENTITY") from exc
            if os.name != "nt":
                descriptor = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            temporary.unlink(missing_ok=True)
        return path


__all__ = ["PATTERN_VERSION", "ObservationWindow", "Pattern",
           "PatternDiscoveryConfig", "PatternDiscoveryEngine",
           "PatternDiscoveryError", "PatternRepository"]
