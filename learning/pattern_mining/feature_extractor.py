"""Deterministic normalization of upstream-approved sample evidence."""
from __future__ import annotations

from typing import Any, Mapping

from .exceptions import PatternMiningError
from .models import ApprovedPatternMiningEvidenceEnvelope, PatternMiningConfig
from .pattern_builder import canonical


def _normalize(mapping: Mapping[str, Any], allowed: tuple[str, ...], config: PatternMiningConfig) -> dict[str, Any]:
    result: dict[str, Any] = {}
    excluded = {x.lower() for x in config.excluded_volatile_fields}
    permitted = set(allowed)
    for key, value in sorted(mapping.items()):
        if key.lower() in excluded or (permitted and key not in permitted):
            continue
        if key.lower() == "rsi" and isinstance(value, (int, float)) and not isinstance(value, bool):
            low, high = config.rsi_bucket_boundaries
            value = "OVERSOLD" if value < low else "OVERBOUGHT" if value > high else "NEUTRAL"
        result[key] = value
    return result


def extract(envelope: ApprovedPatternMiningEvidenceEnvelope, config: PatternMiningConfig) -> tuple[dict[str, Any], ...]:
    if not isinstance(envelope, ApprovedPatternMiningEvidenceEnvelope) or not envelope.approved_samples:
        raise PatternMiningError("MISSING_APPROVED_PATTERN_EVIDENCE")
    identities: dict[str, str] = {}
    rows = []
    for sample in envelope.approved_samples:
        payload = canonical(sample.to_dict())
        if sample.sample_uuid in identities and identities[sample.sample_uuid] != payload:
            raise PatternMiningError("DUPLICATE_CONFLICTING_IDENTITY")
        identities[sample.sample_uuid] = payload
        features = _normalize(sample.features, config.allowed_feature_fields, config)
        if not features:
            raise PatternMiningError("EMPTY_FEATURE_SET")
        contexts = {}
        for name in ("market_context", "entry_context", "exit_context", "risk_context"):
            contexts[name] = _normalize(getattr(sample, name), tuple(config.allowed_context_fields.get(name, ())), config)
        rows.append({"features": features, **contexts, "outcomes": (sample.outcome,)})
    return tuple(rows)
