"""Canonical grouping and candidate construction."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any
from uuid import UUID, uuid5

from .exceptions import PatternMiningError
from .models import CandidatePattern
from .statistics import calculate

_NAMESPACE = UUID("2290f6eb-8e55-5d0d-92f8-6407a420a7c1")


def canonical(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PatternMiningError("INVALID_CANONICAL_EVIDENCE") from exc


def build(rows: tuple[dict[str, Any], ...], total: int, created_at: str) -> tuple[CandidatePattern, ...]:
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        grouping = {key: row[key] for key in ("features", "market_context", "entry_context", "exit_context", "risk_context")}
        key = canonical(grouping)
        signature = sha256(key.encode()).hexdigest()
        if key not in groups:
            groups[key] = dict(row)
            groups[key]["feature_signature"] = signature
            groups[key]["outcomes"] = []
        groups[key]["outcomes"].extend(row["outcomes"])
    patterns = []
    for key in sorted(groups):
        group = groups[key]
        stats = calculate(group["outcomes"], total)
        identity = {"knowledge_uuid": group["knowledge_uuid"], "knowledge_version": group["knowledge_version"],
                    "feature_signature": group["feature_signature"], "outcome_contract": group["outcome_contract"],
                    "market_context": group["market_context"], "entry_context": group["entry_context"],
                    "exit_context": group["exit_context"], "risk_context": group["risk_context"], **stats}
        digest = sha256(canonical(identity).encode()).hexdigest()
        patterns.append(CandidatePattern(str(uuid5(_NAMESPACE, digest)), digest, group["knowledge_uuid"],
                        group["knowledge_version"], group["feature_signature"], group["market_context"],
                        group["entry_context"], group["exit_context"], group["risk_context"], **stats,
                        created_at=created_at))
    return tuple(patterns)
