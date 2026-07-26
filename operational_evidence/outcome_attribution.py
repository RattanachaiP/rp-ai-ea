"""PR205 passive, deterministic attribution of completed-trade outcomes.

The engine consumes only the two immutable public operational-evidence
contracts.  It does not inspect a broker, Runtime, Strategy, or execution
component and deliberately reports unavailable evidence instead of inferring it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
import re
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from runtime.completed_trade_event import CompletedTradeEvent
from runtime.live_outcome_capture import LiveOutcomeRecord


OUTCOME_ATTRIBUTION_VERSION = "PR205-OUTCOME-ATTRIBUTION.1"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class OutcomeAttributionError(ValueError):
    """A fail-closed input, attribution, or persistence failure."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise OutcomeAttributionError("ATTRIBUTION_SERIALIZATION_FAILURE") from exc


def _valid_uuid(value: object) -> bool:
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def _valid_time(value: object) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))  # type: ignore[union-attr]
        normalized = parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")
        return (parsed.tzinfo is not None
                and parsed.utcoffset() == timezone.utc.utcoffset(parsed)
                and value == normalized)
    except (ValueError, TypeError, AttributeError):
        return False


@dataclass(frozen=True, slots=True)
class SupportingEvidence:
    """One factual observation; ``UNAVAILABLE`` is explicit, never inferred."""

    factor: str
    observation: str
    facts: tuple[tuple[str, str | int | float | bool | None], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.factor, str) or not self.factor:
            raise OutcomeAttributionError("INVALID_SUPPORTING_EVIDENCE")
        if self.observation not in {"OBSERVED", "UNAVAILABLE", "NOT_PRESENT_IN_EVIDENCE"}:
            raise OutcomeAttributionError("INVALID_SUPPORTING_EVIDENCE")
        if not isinstance(self.facts, tuple):
            raise OutcomeAttributionError("INVALID_SUPPORTING_EVIDENCE")
        keys: list[str] = []
        for item in self.facts:
            if not isinstance(item, tuple) or len(item) != 2 or not isinstance(item[0], str) or not item[0]:
                raise OutcomeAttributionError("INVALID_SUPPORTING_EVIDENCE")
            value = item[1]
            if not isinstance(value, (str, int, float, bool, type(None))):
                raise OutcomeAttributionError("INVALID_SUPPORTING_EVIDENCE")
            if isinstance(value, float) and not isfinite(value):
                raise OutcomeAttributionError("INVALID_SUPPORTING_EVIDENCE")
            keys.append(item[0])
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise OutcomeAttributionError("INVALID_SUPPORTING_EVIDENCE")

    def to_dict(self) -> dict[str, object]:
        return {"factor": self.factor, "observation": self.observation,
                "facts": {key: value for key, value in self.facts}}


@dataclass(frozen=True, slots=True)
class OutcomeAttribution:
    """Immutable explanation linked to one canonical completed-trade event."""

    attribution_uuid: str
    parent_completed_trade_event_uuid: str
    classification: str
    supporting_evidence: tuple[SupportingEvidence, ...]
    confidence_level: str
    timestamp: str
    replay_identity: str
    source_live_outcome_record_uuid: str
    sha256_digest: str
    contract_version: str = OUTCOME_ATTRIBUTION_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != OUTCOME_ATTRIBUTION_VERSION:
            raise OutcomeAttributionError("ATTRIBUTION_VERSION_MISMATCH")
        for value in (self.attribution_uuid, self.parent_completed_trade_event_uuid,
                      self.replay_identity, self.source_live_outcome_record_uuid):
            if not _valid_uuid(value):
                raise OutcomeAttributionError("INVALID_ATTRIBUTION_UUID")
        if self.classification not in {"PROFITABLE", "LOSS", "BREAKEVEN"}:
            raise OutcomeAttributionError("INVALID_ATTRIBUTION_CLASSIFICATION")
        if self.confidence_level not in {"COMPLETE_OPERATIONAL_EVIDENCE", "PARTIAL_OPERATIONAL_EVIDENCE"}:
            raise OutcomeAttributionError("INVALID_ATTRIBUTION_CONFIDENCE")
        if not _valid_time(self.timestamp):
            raise OutcomeAttributionError("INVALID_ATTRIBUTION_TIMESTAMP")
        if (not isinstance(self.supporting_evidence, tuple)
                or tuple(item.factor for item in self.supporting_evidence) != (
                    "STRATEGY_ALIGNMENT", "ENTRY_TIMING", "EXIT_TIMING",
                    "STOP_LOSS_OUTCOME", "TAKE_PROFIT_OUTCOME", "MANUAL_INTERVENTION",
                    "RISK_PROFILE", "TRADE_DURATION", "LATENCY_OBSERVATIONS",
                    "REPLAY_IDENTITY_VERIFICATION")):
            raise OutcomeAttributionError("INVALID_SUPPORTING_EVIDENCE")
        expected_uuid = self.identity_uuid(self.parent_completed_trade_event_uuid)
        if self.attribution_uuid != expected_uuid:
            raise OutcomeAttributionError("ATTRIBUTION_UUID_MISMATCH")
        expected_digest = sha256(_canonical(self._body())).hexdigest()
        if not _HEX64.fullmatch(self.sha256_digest) or self.sha256_digest != expected_digest:
            raise OutcomeAttributionError("ATTRIBUTION_DIGEST_MISMATCH")

    @staticmethod
    def identity_uuid(parent_event_uuid: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"pr205-outcome-attribution:{parent_event_uuid}"))

    def _body(self) -> dict[str, object]:
        return {
            "attribution_uuid": self.attribution_uuid,
            "parent_completed_trade_event_uuid": self.parent_completed_trade_event_uuid,
            "classification": self.classification,
            "supporting_evidence": [item.to_dict() for item in self.supporting_evidence],
            "confidence_level": self.confidence_level, "timestamp": self.timestamp,
            "replay_identity": self.replay_identity,
            "source_live_outcome_record_uuid": self.source_live_outcome_record_uuid,
            "contract_version": self.contract_version,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._body(), "sha256_digest": self.sha256_digest}

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "OutcomeAttribution":
        """Reconstruct and verify an attribution from its public JSON shape."""
        if not isinstance(value, dict):
            raise OutcomeAttributionError("INVALID_ATTRIBUTION_RECORD")
        values = dict(value)
        raw_evidence = values.get("supporting_evidence")
        if not isinstance(raw_evidence, (list, tuple)):
            raise OutcomeAttributionError("INVALID_SUPPORTING_EVIDENCE")
        try:
            values["supporting_evidence"] = tuple(
                SupportingEvidence(item["factor"], item["observation"],
                                   tuple(sorted(item["facts"].items())))
                for item in raw_evidence
            )
            return cls(**values)  # type: ignore[arg-type]
        except OutcomeAttributionError:
            raise
        except (KeyError, TypeError, AttributeError) as exc:
            raise OutcomeAttributionError("INVALID_ATTRIBUTION_RECORD") from exc


_SHARED_FIELDS = (
    ("decision_uuid", "decision_uuid"),
    ("execution_context_uuid", "execution_context_uuid"),
    ("publication_uuid", "publication_uuid"),
    ("order_ticket", "order_ticket"), ("deal_ticket", "deal_ticket"),
    ("position_ticket", "position_ticket"),
    ("publication_timestamp", "publication_timestamp"),
    ("consumer_acceptance_timestamp", "consumer_acceptance_timestamp"),
    ("activation_timestamp", "activation_timestamp"),
    ("order_send_timestamp", "order_send_timestamp"),
    ("open_time", "position_open_timestamp"), ("close_time", "position_close_timestamp"),
    ("capture_time", "captured_at"), ("symbol", "symbol"), ("direction", "direction"),
    ("volume", "volume"), ("entry_price", "entry_price"), ("exit_price", "exit_price"),
    ("exit_reason", "exit_reason"), ("stop_loss", "stop_loss"),
    ("take_profit", "take_profit"), ("broker_response_code", "broker_response_code"),
    ("account_number", "account_number"), ("server_name", "server_name"),
    ("gross_profit", "gross_profit"), ("net_profit", "net_profit"),
    ("commission", "commission"), ("swap", "swap"),
    ("maximum_favorable_excursion", "maximum_favorable_excursion"),
    ("maximum_adverse_excursion", "maximum_adverse_excursion"),
)


def _facts(**values: str | int | float | bool | None) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted(values.items()))


class OutcomeAttributionEngine:
    """Derive descriptive facts without recommendations or execution authority."""

    def attribute(self, completed: CompletedTradeEvent,
                  live_outcome: LiveOutcomeRecord) -> OutcomeAttribution:
        if type(completed) is not CompletedTradeEvent:
            raise OutcomeAttributionError("COMPLETED_TRADE_EVENT_REQUIRED")
        if type(live_outcome) is not LiveOutcomeRecord:
            raise OutcomeAttributionError("LIVE_OUTCOME_RECORD_REQUIRED")
        # Reconstruction re-runs each source contract's immutable integrity checks.
        try:
            completed = CompletedTradeEvent(**completed.to_dict())  # type: ignore[arg-type]
            values = live_outcome.to_dict()
            values["replay_identity_chain"] = tuple(values["replay_identity_chain"])  # type: ignore[arg-type]
            live_outcome = LiveOutcomeRecord(**values)  # type: ignore[arg-type]
        except (TypeError, ValueError, AttributeError) as exc:
            raise OutcomeAttributionError("INVALID_IMMUTABLE_SOURCE") from exc
        if any(getattr(completed, event_name) != getattr(live_outcome, record_name)
               for event_name, record_name in _SHARED_FIELDS):
            raise OutcomeAttributionError("OPERATIONAL_EVIDENCE_MISMATCH")
        if (live_outcome.replay_identity_chain[0] != completed.replay_identity
                or live_outcome.replay_identity_chain[1] != completed.decision_uuid
                or live_outcome.replay_identity_chain[2] != completed.execution_context_uuid
                or live_outcome.parent_decision_uuid != completed.decision_uuid
                or live_outcome.parent_execution_context_uuid != completed.execution_context_uuid):
            raise OutcomeAttributionError("REPLAY_IDENTITY_MISMATCH")

        reason = completed.exit_reason.upper().replace("-", "_").replace(" ", "_")
        manual = "MANUAL" in reason
        evidence = (
            SupportingEvidence("STRATEGY_ALIGNMENT", "UNAVAILABLE", ()),
            SupportingEvidence("ENTRY_TIMING", "OBSERVED", _facts(
                entry_price=completed.entry_price, position_open_timestamp=completed.open_time)),
            SupportingEvidence("EXIT_TIMING", "OBSERVED", _facts(
                exit_price=completed.exit_price, exit_reason=completed.exit_reason,
                position_close_timestamp=completed.close_time)),
            SupportingEvidence("STOP_LOSS_OUTCOME", "OBSERVED", _facts(
                configured_stop_loss=completed.stop_loss,
                exit_reason_indicates_stop_loss=reason in {"SL", "STOP", "STOP_LOSS"})),
            SupportingEvidence("TAKE_PROFIT_OUTCOME", "OBSERVED", _facts(
                configured_take_profit=completed.take_profit,
                exit_reason_indicates_take_profit=reason in {"TP", "TAKE_PROFIT"})),
            SupportingEvidence("MANUAL_INTERVENTION", "OBSERVED" if manual else "NOT_PRESENT_IN_EVIDENCE",
                               _facts(exit_reason=completed.exit_reason,
                                      exit_reason_indicates_manual=manual)),
            SupportingEvidence("RISK_PROFILE", "OBSERVED", _facts(
                direction=completed.direction, entry_price=completed.entry_price,
                stop_loss=completed.stop_loss, take_profit=completed.take_profit,
                volume=completed.volume)),
            SupportingEvidence("TRADE_DURATION", "OBSERVED", _facts(
                trade_duration_seconds=live_outcome.trade_duration_seconds)),
            SupportingEvidence("LATENCY_OBSERVATIONS", "OBSERVED", _facts(
                execution_latency_seconds=live_outcome.execution_latency_seconds)),
            SupportingEvidence("REPLAY_IDENTITY_VERIFICATION", "OBSERVED", _facts(
                event_replay_identity=completed.replay_identity,
                replay_identity_verified=True)),
        )
        classification = ("PROFITABLE" if completed.net_profit > 0 else
                          "LOSS" if completed.net_profit < 0 else "BREAKEVEN")
        identifier = OutcomeAttribution.identity_uuid(completed.event_uuid)
        unsigned = {
            "attribution_uuid": identifier,
            "parent_completed_trade_event_uuid": completed.event_uuid,
            "classification": classification, "supporting_evidence": evidence,
            # Complete means the two required source records were verified.  It
            # does not imply that Strategy evidence, which is outside them, exists.
            "confidence_level": "COMPLETE_OPERATIONAL_EVIDENCE",
            "timestamp": completed.capture_time,
            "replay_identity": completed.replay_identity,
            "source_live_outcome_record_uuid": live_outcome.record_uuid,
            "contract_version": OUTCOME_ATTRIBUTION_VERSION,
        }
        body = {**unsigned, "supporting_evidence": [item.to_dict() for item in evidence]}
        return OutcomeAttribution(**unsigned, sha256_digest=sha256(_canonical(body)).hexdigest())


class OutcomeAttributionRepository:
    """Append-only operational-evidence repository for attribution records."""

    def __init__(self, root: str | Path = "operational_evidence") -> None:
        self.root = Path(root)

    def append(self, attribution: OutcomeAttribution) -> Path:
        if type(attribution) is not OutcomeAttribution:
            raise TypeError("OUTCOME_ATTRIBUTION_REQUIRED")
        # Reconstruction rejects forged or mutated source values.
        attribution = OutcomeAttribution.from_dict(attribution.to_dict())
        directory = self.root / "outcome_attributions"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"outcome_attribution_{attribution.attribution_uuid}.json"
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(_canonical(attribution.to_dict()) + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise OutcomeAttributionError("DUPLICATE_ATTRIBUTION") from exc
            if os.name != "nt":
                descriptor = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            temporary.unlink(missing_ok=True)
        return path


__all__ = ["OUTCOME_ATTRIBUTION_VERSION", "OutcomeAttributionError",
           "SupportingEvidence", "OutcomeAttribution", "OutcomeAttributionEngine",
           "OutcomeAttributionRepository"]
