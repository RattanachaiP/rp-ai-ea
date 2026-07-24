"""Repository coordinating validated, append-only lifecycle transitions."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
from typing import Iterator

from .schema import INITIAL_STATE
from .storage import LifecycleStorage
from .transition import LifecycleTransition
from .validator import LifecycleValidator


class LifecycleRepository:
    """State-recording repository deliberately isolated from runtime consumers."""

    def __init__(self, root: str | Path = "learning_data") -> None:
        self.storage = LifecycleStorage(root)
        self.validator = LifecycleValidator()

    @contextmanager
    def _lock(self, knowledge_uuid: str) -> Iterator[None]:
        """Serialize read/validate/write for one knowledge identity across processes."""
        import fcntl
        lock_name = hashlib.sha256(knowledge_uuid.encode("utf-8")).hexdigest()
        directory = self.storage.directory
        directory.mkdir(parents=True, exist_ok=True)
        lock_path = directory / f".transition-{lock_name}.lock"
        with lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def append(self, transition: LifecycleTransition) -> Path:
        with self._lock(transition.knowledge_uuid):
            existing = self.history(transition.knowledge_uuid)
            # Replay of an already published event is safe and does not alter history.
            for prior in existing:
                if prior.transition_uuid == transition.transition_uuid:
                    if prior.to_dict() == transition.to_dict():
                        return self.storage.path_for(transition.transition_uuid)
                    raise FileExistsError("LIFECYCLE_IMMUTABLE")
            self.validator.validate(transition, existing)
            return self.storage.write(transition)

    def history(self, knowledge_uuid: str) -> tuple[LifecycleTransition, ...]:
        records = [item for item in self.storage.all() if item.knowledge_uuid == knowledge_uuid]
        return tuple(sorted(records, key=lambda item: (item.timestamp, item.transition_uuid)))

    def current_state(self, knowledge_uuid: str) -> str:
        entries = self.history(knowledge_uuid)
        return entries[-1].new_state if entries else INITIAL_STATE

    def timeline(self, knowledge_uuid: str) -> tuple[dict[str, str], ...]:
        """Return immutable serialisable audit events in replay order."""
        return tuple(item.to_dict() for item in self.history(knowledge_uuid))
