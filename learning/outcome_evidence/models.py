"""Immutable PR250 acquisition contracts and canonical identity functions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping
from uuid import UUID, uuid5

SCHEMA_VERSION = "PR250.OUTCOME_EVIDENCE.1.0"
REPLAY_DOMAIN = b"RP-AI-EA/PR250/ROW-REPLAY/V1\x00"
MANIFEST_DOMAIN = b"RP-AI-EA/PR250/MANIFEST/V1\x00"
RECORD_NAMESPACE = UUID("b367a539-dddd-5b51-9671-da7c13c7f2b1")
REQUIRED_ROW_FIELDS = (
    "knowledge_uuid", "knowledge_version", "timestamp", "replay_digest",
    "outcome", "outcome_metric", "outcome_unit",
)
OPTIONAL_ROW_FIELDS = ("features", "indicators", "risk_factors", "context", "metadata")


class OutcomeEvidenceError(ValueError):
    """Fail-closed diagnostic with operator recovery information."""

    def __init__(self, code: str, next_action: str, *, mutation_occurred: bool = False):
        self.code = code
        self.mutation_occurred = mutation_occurred
        self.rerun_safe = True
        self.next_action = next_action
        super().__init__(
            f"{code} mutation_occurred={str(mutation_occurred).lower()} rerun_safe=true "
            f"next_action={next_action}"
        )


def canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise OutcomeEvidenceError(
            "OUTCOME_EVIDENCE_SCHEMA_INVALID",
            "replace unsupported or non-finite values at the authoritative source",
        ) from exc


def _canonical_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float) and isfinite(value):
        return value
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) or not key for key in value):
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID",
                                       "use non-empty string keys in canonical nested values")
        return {key: _canonical_value(value[key]) for key in sorted(value)}
    raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID",
                               "replace unsupported nested values at the authoritative source")


def _timestamp(value: Any, field: str = "timestamp") -> str:
    if not isinstance(value, str):
        raise OutcomeEvidenceError("TIMESTAMP_INVALID", f"supply a timezone-aware ISO-8601 {field}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
    except ValueError as exc:
        raise OutcomeEvidenceError("TIMESTAMP_INVALID", f"supply a timezone-aware ISO-8601 {field}") from exc
    return value


def row_replay_digest(row_without_replay_digest: Mapping[str, Any]) -> str:
    """Acquisition-owned replay identity over the complete immutable event row."""
    return sha256(REPLAY_DOMAIN + canonical_json(row_without_replay_digest)).hexdigest()


@dataclass(frozen=True)
class OutcomeEvidenceRow:
    """Named immutable input accepted by the existing PR173 engine."""

    values: Mapping[str, Any]

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "OutcomeEvidenceRow":
        if not isinstance(raw, Mapping) or any(field not in raw for field in REQUIRED_ROW_FIELDS):
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID",
                                       "supply every required PR173 evidence-row field")
        unknown = set(raw) - set(REQUIRED_ROW_FIELDS) - set(OPTIONAL_ROW_FIELDS)
        if unknown:
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID",
                                       "move explicitly governed extra fields into row metadata")
        try:
            knowledge_uuid = str(UUID(str(raw["knowledge_uuid"])))
        except (ValueError, TypeError, AttributeError) as exc:
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID",
                                       "supply the authoritative valid knowledge UUID") from exc
        if not isinstance(raw["knowledge_version"], str) or not raw["knowledge_version"]:
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID",
                                       "supply a non-empty knowledge version")
        timestamp = _timestamp(raw["timestamp"])
        outcome = raw["outcome"]
        if isinstance(outcome, bool) or not isinstance(outcome, (int, float)) or not isfinite(outcome):
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID",
                                       "supply a finite numeric completed outcome")
        if not isinstance(raw["outcome_metric"], str) or not raw["outcome_metric"] or not isinstance(raw["outcome_unit"], str) or not raw["outcome_unit"]:
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID",
                                       "supply a non-empty string outcome metric and unit")
        normalized = {
            "knowledge_uuid": knowledge_uuid,
            "knowledge_version": raw["knowledge_version"],
            "timestamp": timestamp,
            "outcome": float(outcome),
            "outcome_metric": raw["outcome_metric"],
            "outcome_unit": raw["outcome_unit"],
        }
        for field in OPTIONAL_ROW_FIELDS:
            if field in raw:
                if not isinstance(raw[field], Mapping):
                    raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID",
                                               f"supply {field} as a canonical object")
                normalized[field] = _canonical_value(raw[field])
            elif field != "metadata":
                normalized[field] = {}
        expected = row_replay_digest(normalized)
        supplied = raw["replay_digest"]
        if not isinstance(supplied, str) or supplied.lower() != expected:
            raise OutcomeEvidenceError("REPLAY_PROVENANCE_INVALID",
                                       "re-export the complete immutable source event with its PR250 replay digest")
        normalized["replay_digest"] = expected
        return cls(MappingProxyType(normalized))

    def to_dict(self) -> dict[str, Any]:
        return json.loads(canonical_json(dict(self.values)))


def manifest_digest(payload_without_digest: Mapping[str, Any]) -> str:
    payload = dict(payload_without_digest)
    if isinstance(payload.get("evidence_rows"), list):
        payload["evidence_rows"] = sorted(payload["evidence_rows"], key=canonical_json)
    return sha256(MANIFEST_DOMAIN + canonical_json(payload)).hexdigest()


@dataclass(frozen=True)
class OutcomeEvidenceManifest:
    schema_version: str
    source_system_identity: str
    acquisition_timestamp: str
    operator_metadata: Mapping[str, Any]
    declared_knowledge_identity: Mapping[str, str]
    declared_outcome_contract: Mapping[str, str]
    evidence_rows: tuple[OutcomeEvidenceRow, ...]
    manifest_digest: str
    external_source_reference: str | None = None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "OutcomeEvidenceManifest":
        fields = {"schema_version", "source_system_identity", "acquisition_timestamp",
                  "operator_metadata", "declared_knowledge_identity", "declared_outcome_contract",
                  "evidence_rows", "manifest_digest", "external_source_reference"}
        required = fields - {"external_source_reference"}
        if not isinstance(raw, Mapping) or set(raw) - fields or not required.issubset(raw):
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID",
                                       "use the exact PR250 canonical manifest field set")
        if raw["schema_version"] != SCHEMA_VERSION:
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID",
                                       f"use schema_version {SCHEMA_VERSION}")
        if not isinstance(raw["source_system_identity"], str) or not raw["source_system_identity"]:
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID",
                                       "supply the non-secret authoritative source-system identity")
        acquired = _timestamp(raw["acquisition_timestamp"], "acquisition_timestamp")
        for field in ("operator_metadata", "declared_knowledge_identity", "declared_outcome_contract"):
            if not isinstance(raw[field], Mapping):
                raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID", f"supply {field} as an object")
        operator = _canonical_value(raw["operator_metadata"])
        identity = _canonical_value(raw["declared_knowledge_identity"])
        contract = _canonical_value(raw["declared_outcome_contract"])
        if set(identity) != {"knowledge_uuid", "knowledge_version"}:
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID", "declare the exact knowledge UUID and version")
        try:
            identity["knowledge_uuid"] = str(UUID(str(identity["knowledge_uuid"])))
        except (ValueError, TypeError, AttributeError) as exc:
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID", "declare a valid knowledge UUID") from exc
        if set(contract) != {"outcome_metric", "outcome_unit"}:
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID", "declare the exact outcome metric and unit")
        rows_raw = raw["evidence_rows"]
        if not isinstance(rows_raw, list) or not rows_raw:
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_EMPTY", "supply at least one real completed-outcome row")
        rows = tuple(OutcomeEvidenceRow.from_dict(row) for row in rows_raw)
        identities = {(r.values["knowledge_uuid"], r.values["knowledge_version"]) for r in rows}
        if identities != {(identity["knowledge_uuid"], identity["knowledge_version"])}:
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_IDENTITY_MISMATCH", "split evidence by exact declared knowledge identity")
        contracts = {(r.values["outcome_metric"], r.values["outcome_unit"]) for r in rows}
        if contracts != {(contract["outcome_metric"], contract["outcome_unit"])}:
            raise OutcomeEvidenceError("OUTCOME_CONTRACT_MISMATCH", "split evidence by exact declared outcome contract")
        reference = raw.get("external_source_reference")
        if reference is not None and (not isinstance(reference, str) or not reference or "secret" in reference.lower()):
            raise OutcomeEvidenceError("OUTCOME_EVIDENCE_SCHEMA_INVALID", "use a non-secret external source reference")
        normalized_rows = sorted((row.to_dict() for row in rows),
                                 key=lambda row: (datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")), canonical_json(row)))
        payload = {"schema_version": SCHEMA_VERSION, "source_system_identity": raw["source_system_identity"],
                   "acquisition_timestamp": acquired, "operator_metadata": operator,
                   "declared_knowledge_identity": identity, "declared_outcome_contract": contract,
                   "evidence_rows": normalized_rows}
        if reference is not None:
            payload["external_source_reference"] = reference
        expected = manifest_digest(payload)
        if raw["manifest_digest"] != expected:
            raise OutcomeEvidenceError("SOURCE_DIGEST_MISMATCH", "re-export the canonical manifest and its digest")
        return cls(SCHEMA_VERSION, raw["source_system_identity"], acquired,
                   MappingProxyType(operator), MappingProxyType(identity), MappingProxyType(contract),
                   tuple(OutcomeEvidenceRow.from_dict(row) for row in normalized_rows), expected, reference)

    def to_dict(self) -> dict[str, Any]:
        value = {"schema_version": self.schema_version, "source_system_identity": self.source_system_identity,
                 "acquisition_timestamp": self.acquisition_timestamp,
                 "operator_metadata": dict(self.operator_metadata),
                 "declared_knowledge_identity": dict(self.declared_knowledge_identity),
                 "declared_outcome_contract": dict(self.declared_outcome_contract),
                 "evidence_rows": [row.to_dict() for row in self.evidence_rows],
                 "manifest_digest": self.manifest_digest}
        if self.external_source_reference is not None:
            value["external_source_reference"] = self.external_source_reference
        return value
