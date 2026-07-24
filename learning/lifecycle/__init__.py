"""Independent, append-only lifecycle framework for Verified Knowledge."""
from .lifecycle import current_state, history, timeline, transition
from .repository import LifecycleRepository
from .schema import ALLOWED_TRANSITIONS, INITIAL_STATE, LIFECYCLE_SCHEMA_VERSION, LIFECYCLE_STATES
from .storage import LifecycleStorage
from .transition import LifecycleTransition
from .validator import LifecycleValidationError, LifecycleValidator, validate_transition

__all__ = [
    "ALLOWED_TRANSITIONS", "INITIAL_STATE", "LIFECYCLE_SCHEMA_VERSION", "LIFECYCLE_STATES",
    "LifecycleRepository", "LifecycleStorage", "LifecycleTransition", "LifecycleValidationError",
    "LifecycleValidator", "current_state", "history", "timeline", "transition", "validate_transition",
]
