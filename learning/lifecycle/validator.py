"""Deterministic validation for Knowledge Lifecycle audit events."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable
from uuid import UUID

from .schema import ALLOWED_TRANSITIONS, INITIAL_STATE, LIFECYCLE_SCHEMA_VERSION, LIFECYCLE_STATES
from .transition import LifecycleTransition


class LifecycleValidationError(ValueError):
    """Raised when a lifecycle event cannot be accepted into immutable history."""


def validate_transition(previous_state: str, new_state: str) -> None:
    if previous_state not in LIFECYCLE_STATES or new_state not in LIFECYCLE_STATES:
        raise LifecycleValidationError("INVALID_LIFECYCLE_STATE")
    if new_state not in ALLOWED_TRANSITIONS[previous_state]:
        raise LifecycleValidationError("INVALID_LIFECYCLE_TRANSITION")


class LifecycleValidator:
    def validate_artifact(self, transition: LifecycleTransition) -> datetime:
        """Validate rules which do not require storage-backed history."""
        for field in ("knowledge_uuid", "triggering_component", "reason", "governance_version", "lifecycle_version"):
            if not isinstance(getattr(transition, field), str) or not getattr(transition, field):
                raise LifecycleValidationError("REQUIRED_FIELDS")
        if transition.schema_version != LIFECYCLE_SCHEMA_VERSION:
            raise LifecycleValidationError("INVALID_SCHEMA_VERSION")
        try:
            parsed_timestamp = datetime.fromisoformat(transition.timestamp.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise LifecycleValidationError("INVALID_TIMESTAMP") from exc
        if parsed_timestamp.tzinfo is None:
            raise LifecycleValidationError("INVALID_TIMESTAMP")
        try:
            UUID(transition.transition_uuid)
        except (AttributeError, ValueError) as exc:
            raise LifecycleValidationError("INVALID_TRANSITION_UUID") from exc
        validate_transition(transition.previous_state, transition.new_state)
        return parsed_timestamp

    def validate(self, transition: LifecycleTransition,
                 history: Iterable[LifecycleTransition] = ()) -> None:
        parsed_timestamp = self.validate_artifact(transition)

        prior = list(history)
        if not prior:
            if transition.previous_state != INITIAL_STATE:
                raise LifecycleValidationError("INVALID_INITIAL_STATE")
            return

        last = prior[-1]
        if transition.previous_state != last.new_state:
            raise LifecycleValidationError("STALE_PREVIOUS_STATE")
        last_timestamp = datetime.fromisoformat(last.timestamp.replace("Z", "+00:00"))
        if parsed_timestamp <= last_timestamp:
            raise LifecycleValidationError("NON_MONOTONIC_TIMESTAMP")
