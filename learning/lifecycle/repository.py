"""Repository coordinating validated, append-only lifecycle transitions."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import time
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
        """Portable interprocess lock using atomic lock-file creation."""
        lock_name = hashlib.sha256(knowledge_uuid.encode("utf-8")).hexdigest()
        directory = self.storage.directory
        directory.mkdir(parents=True, exist_ok=True)
        lock_path = directory / f".transition-{lock_name}.lock"
        deadline = time.monotonic() + 10.0
        descriptor: int | None = None
        while descriptor is None:
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("LIFECYCLE_LOCK_TIMEOUT")
                time.sleep(0.01)
        try:
            os.write(descriptor, str(os.getpid()).encode("ascii"))
            os.fsync(descriptor)
            yield
        finally:
            os.close(descriptor)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    def append(self, transition: LifecycleTransition) -> Path:
        with self._lock(transition.knowledge_uuid):
            existing = self.history(transition.knowledge_uuid)
            for prior in existing:
                if prior.transition_uuid == transition.transition_uuid:
                    if prior.to_dict() == transition.to_dict():
                        return self.storage.path_for(transition.transition_uuid)
                    raise FileExistsError("LIFECYCLE_IMMUTABLE")
            self.validator.validate(transition, existing)
            return self.storage.write(transition)

    def history(self, knowledge_uuid: str) -> tuple[LifecycleTransition, ...]:
        records = [item for item in self.storage.all() if item.knowledge_uuid == knowledge_uuid]
        return tuple(sorted(records, key=lambda item: item.timestamp))

    def current_state(self, knowledge_uuid: str) -> str:
        entries = self.history(knowledge_uuid)
        return entries[-1].new_state if entries else INITIAL_STATE

    def timeline(self, knowledge_uuid: str) -> tuple[dict[str, str], ...]:
        """Return immutable serialisable audit events in replay order."""
        return tuple(item.to_dict() for item in self.history(knowledge_uuid))
