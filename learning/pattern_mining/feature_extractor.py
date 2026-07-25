"""Extraction from the policy report's approved evidence envelope."""
from __future__ import annotations

from math import isfinite
from typing import Any, Mapping

from .exceptions import PatternMiningError
from .pattern_builder import canonical


def extract(report: Any) -> tuple[dict[str, Any], ...]:
    summary = report.validation_summary
    evidence = summary.get("approved_evidence") if isinstance(summary, Mapping) else None
    if evidence is None:
        contract = summary.get("outcome_contract") if isinstance(summary, Mapping) else None
        if not isinstance(contract, (list, tuple)) or len(contract) != 2 or not all(isinstance(x, str) and x for x in contract):
            raise PatternMiningError("EMPTY_FEATURE_SET")
        # PR174 currently exposes aggregate approval only. Preserve that limitation:
        # the aggregate is neutral evidence and no unapproved outcome is inferred.
        return ({"knowledge_uuid": report.knowledge_uuid, "knowledge_version": report.knowledge_version,
                 "outcome_contract": tuple(contract), "features": {"outcome_contract": list(contract)},
                 "market_context": {}, "entry_context": {}, "exit_context": {}, "risk_context": {},
                 "outcomes": tuple(0.0 for _ in range(report.sample_count))},)
    if not isinstance(evidence, (list, tuple)) or not evidence:
        raise PatternMiningError("EMPTY_FEATURE_SET")
    rows = []
    evidence_identities: dict[str, str] = {}
    for row in evidence:
        if not isinstance(row, Mapping) or not isinstance(row.get("features"), Mapping) or not row["features"]:
            raise PatternMiningError("EMPTY_FEATURE_SET")
        knowledge_uuid = row.get("knowledge_uuid", report.knowledge_uuid)
        knowledge_version = row.get("knowledge_version", report.knowledge_version)
        contract = tuple(row.get("outcome_contract", summary.get("outcome_contract", ())))
        outcome = row.get("outcome")
        if ((knowledge_uuid, knowledge_version) != (report.knowledge_uuid, report.knowledge_version)):
            raise PatternMiningError("MIXED_KNOWLEDGE_UUID")
        if len(contract) != 2:
            raise PatternMiningError("MIXED_OUTCOME_CONTRACT")
        if isinstance(outcome, bool) or not isinstance(outcome, (int, float)) or not isfinite(outcome):
            raise PatternMiningError("INVALID_STATISTICS")
        contexts = {}
        for name in ("market_context", "entry_context", "exit_context", "risk_context"):
            value = row.get(name, {})
            if not isinstance(value, Mapping):
                raise PatternMiningError("INVALID_CONTEXT")
            contexts[name] = dict(value)
        evidence_identity = row.get("evidence_uuid", row.get("sample_uuid"))
        if evidence_identity is not None:
            if not isinstance(evidence_identity, str) or not evidence_identity:
                raise PatternMiningError("INVALID_EVIDENCE_IDENTITY")
            content = canonical(dict(row))
            if evidence_identity in evidence_identities and evidence_identities[evidence_identity] != content:
                raise PatternMiningError("DUPLICATE_CONFLICTING_IDENTITY")
            evidence_identities[evidence_identity] = content
        rows.append({"knowledge_uuid": knowledge_uuid, "knowledge_version": knowledge_version,
                     "outcome_contract": contract, "features": dict(row["features"]),
                     "outcomes": (float(outcome),), **contexts})
    return tuple(rows)
