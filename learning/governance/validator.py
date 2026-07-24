"""Validation for passive governance metadata and lifecycle transitions."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .models import KnowledgeGovernance
from .schema import ALLOWED_TRANSITIONS, GOVERNANCE_SCHEMA_VERSION, LIFECYCLE_STATES


class GovernanceValidationError(ValueError):
    pass


def _timestamp(value: str | None, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise GovernanceValidationError(f"INVALID_{field}")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GovernanceValidationError(f"INVALID_{field}") from exc
    if result.tzinfo is None:
        raise GovernanceValidationError(f"INVALID_{field}")
    return result


class LifecycleValidator:
    """Enforces only metadata shape and explicit lifecycle progression."""

    def validate(self, governance: KnowledgeGovernance, existing: Iterable[KnowledgeGovernance] = ()) -> None:
        required = (
            "knowledge_uuid", "pattern_uuid", "validation_uuid", "analytics_uuid",
            "source_baseline_commit", "rule_version", "analytics_version", "lineage_reference",
        )
        if any(not isinstance(getattr(governance, field), str) or not getattr(governance, field) for field in required):
            raise GovernanceValidationError("REQUIRED_FIELDS")
        if governance.schema_version != GOVERNANCE_SCHEMA_VERSION:
            raise GovernanceValidationError("INVALID_SCHEMA_VERSION")
        if governance.current_lifecycle_state not in LIFECYCLE_STATES:
            raise GovernanceValidationError("INVALID_LIFECYCLE_STATE")
        if not isinstance(governance.production_eligible, bool):
            raise GovernanceValidationError("INVALID_PRODUCTION_ELIGIBILITY")
        if governance.production_eligible and governance.current_lifecycle_state != "ACTIVE":
            raise GovernanceValidationError("INELIGIBLE_LIFECYCLE_STATE")
        if not isinstance(governance.record_version, int) or isinstance(governance.record_version, bool) or governance.record_version < 1:
            raise GovernanceValidationError("INVALID_RECORD_VERSION")

        promoted = _timestamp(governance.promotion_timestamp, "PROMOTION_TIMESTAMP")
        retired = _timestamp(governance.retirement_timestamp, "RETIREMENT_TIMESTAMP")
        # ARCHIVED may be reached directly from DRAFT/VERIFIED and therefore does not
        # inherently prove that promotion ever occurred. Promotion is mandatory only
        # for states that necessarily descend from ACTIVE.
        if governance.current_lifecycle_state in {"ACTIVE", "SUPERSEDED", "RETIRED"} and promoted is None:
            raise GovernanceValidationError("PROMOTION_TIMESTAMP_REQUIRED")
        if governance.current_lifecycle_state == "RETIRED" and retired is None:
            raise GovernanceValidationError("RETIREMENT_TIMESTAMP_REQUIRED")
        if governance.current_lifecycle_state != "RETIRED" and retired is not None:
            raise GovernanceValidationError("RETIREMENT_TIMESTAMP_NOT_ALLOWED")
        if promoted is not None and retired is not None and retired < promoted:
            raise GovernanceValidationError("RETIREMENT_BEFORE_PROMOTION")

        history = sorted(
            (item for item in existing if item.knowledge_uuid == governance.knowledge_uuid),
            key=lambda item: item.record_version,
        )
        if not history:
            if governance.record_version != 1:
                raise GovernanceValidationError("INVALID_RECORD_VERSION_SEQUENCE")
            return

        prior = history[-1]
        if governance.record_version != prior.record_version + 1:
            raise GovernanceValidationError("INVALID_RECORD_VERSION_SEQUENCE")
        immutable = (
            "knowledge_uuid", "pattern_uuid", "validation_uuid", "analytics_uuid",
            "source_baseline_commit", "rule_version", "analytics_version",
            "lineage_reference", "schema_version",
        )
        if any(getattr(governance, field) != getattr(prior, field) for field in immutable):
            raise GovernanceValidationError("GOVERNANCE_IDENTITY_IMMUTABLE")
        if governance.current_lifecycle_state not in ALLOWED_TRANSITIONS[prior.current_lifecycle_state]:
            raise GovernanceValidationError("INVALID_LIFECYCLE_TRANSITION")
        if prior.promotion_timestamp is not None and governance.promotion_timestamp != prior.promotion_timestamp:
            raise GovernanceValidationError("PROMOTION_TIMESTAMP_IMMUTABLE")
        if prior.retirement_timestamp is not None and governance.retirement_timestamp != prior.retirement_timestamp:
            raise GovernanceValidationError("RETIREMENT_TIMESTAMP_IMMUTABLE")
