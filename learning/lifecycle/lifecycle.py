"""Public lifecycle operations for Verified Knowledge state recording only."""
from __future__ import annotations

from pathlib import Path

from .repository import LifecycleRepository
from .transition import LifecycleTransition
from .validator import validate_transition


def transition(*, knowledge_uuid: str, previous_state: str, new_state: str,
               triggering_component: str, reason: str, governance_version: str,
               lifecycle_version: str, timestamp: str | None = None,
               transition_uuid: str | None = None,
               repository: LifecycleRepository | None = None,
               root: str | Path = "learning_data") -> LifecycleTransition:
    """Validate and append one caller-triggered lifecycle transition.

    This function records metadata only; it does not promote, retire, or authorise
    knowledge for runtime use.
    """
    event = LifecycleTransition.create(
        knowledge_uuid=knowledge_uuid, previous_state=previous_state, new_state=new_state,
        triggering_component=triggering_component, reason=reason,
        governance_version=governance_version, lifecycle_version=lifecycle_version,
        timestamp=timestamp, transition_uuid=transition_uuid,
    )
    (repository or LifecycleRepository(root)).append(event)
    return event


def history(knowledge_uuid: str, *, repository: LifecycleRepository | None = None,
            root: str | Path = "learning_data") -> tuple[LifecycleTransition, ...]:
    return (repository or LifecycleRepository(root)).history(knowledge_uuid)


def current_state(knowledge_uuid: str, *, repository: LifecycleRepository | None = None,
                  root: str | Path = "learning_data") -> str:
    return (repository or LifecycleRepository(root)).current_state(knowledge_uuid)


def timeline(knowledge_uuid: str, *, repository: LifecycleRepository | None = None,
             root: str | Path = "learning_data") -> tuple[dict[str, str], ...]:
    return (repository or LifecycleRepository(root)).timeline(knowledge_uuid)
