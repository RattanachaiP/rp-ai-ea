"""Canonical grouping and provenance-bound candidate construction."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any
from uuid import UUID, uuid5

from .exceptions import PatternMiningError
from .models import ApprovedPatternMiningEvidenceEnvelope, CandidatePattern, PatternMiningConfig
from .statistics import calculate

_NAMESPACE = UUID("2290f6eb-8e55-5d0d-92f8-6407a420a7c1")


def canonical(value: Any) -> str:
    try: return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc: raise PatternMiningError("INVALID_CANONICAL_EVIDENCE") from exc


def build(rows: tuple[dict[str, Any], ...], envelope: ApprovedPatternMiningEvidenceEnvelope,
          config: PatternMiningConfig, engine_version: str) -> tuple[CandidatePattern, ...]:
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        grouping = {key: row[key] for key in ("features", "market_context", "entry_context", "exit_context", "risk_context")}
        key = canonical(grouping)
        if key not in groups: groups[key] = {**row, "outcomes": []}
        groups[key]["outcomes"].extend(row["outcomes"])
    patterns = []
    for key in sorted(groups):
        group = groups[key]; signature = sha256(key.encode()).hexdigest()
        stats = calculate(group["outcomes"], len(envelope.approved_samples))
        identity = {"policy_uuid": envelope.policy_uuid, "policy_version": envelope.policy_version,
                    "engine_version": engine_version, "source_attribution_uuid": envelope.source_attribution_uuid,
                    "source_digest": envelope.source_digest, "replay_digest": envelope.replay_digest,
                    "knowledge_uuid": envelope.knowledge_uuid, "knowledge_version": envelope.knowledge_version,
                    "outcome_contract": envelope.outcome_contract, "feature_signature": signature,
                    "config": config.to_dict(), **{x: group[x] for x in ("market_context", "entry_context", "exit_context", "risk_context")}, **stats}
        digest = sha256(canonical(identity).encode()).hexdigest()
        patterns.append(CandidatePattern(str(uuid5(_NAMESPACE, digest)), digest, envelope.policy_uuid, envelope.policy_version,
                        envelope.source_attribution_uuid, envelope.replay_digest, engine_version, envelope.knowledge_uuid,
                        envelope.knowledge_version, envelope.outcome_contract, signature, group["market_context"], group["entry_context"],
                        group["exit_context"], group["risk_context"], **stats, created_at=envelope.generated_at, advisory_only=True))
    return tuple(patterns)
