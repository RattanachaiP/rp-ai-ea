"""Crash-safe atomic publication and single-writer ownership for decision.json."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Mapping
from .decision_contract import validate_pr_a_decision


class PublicationError(OSError):
    pass


class OwnershipError(RuntimeError):
    pass


class DecisionPathOwnership:
    """Explicit process-lifetime ownership; stale locks require operator reset."""
    def __init__(self, decision_path: str | Path) -> None:
        self.path = Path(decision_path).with_name(Path(decision_path).name + ".v28.lock")
        self._owned = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="ascii") as stream:
                stream.write(str(os.getpid()))
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as error:
            raise OwnershipError("DECISION_PATH_OWNERSHIP_UNAVAILABLE") from error
        self._owned = True

    def release(self) -> None:
        if self._owned:
            try:
                self.path.unlink()
            finally:
                self._owned = False

    def __enter__(self) -> "DecisionPathOwnership":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


class AtomicDecisionPublisher:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.temporary = self.path.with_name(self.path.name + ".tmp")

    def cleanup_stale_temporary(self) -> None:
        try:
            self.temporary.unlink()
        except FileNotFoundError:
            pass
        except OSError as error:
            raise PublicationError("STALE_TEMPORARY_CLEANUP_FAILED") from error

    def publish(self, decision: Mapping[str, Any]) -> None:
        validate_pr_a_decision(dict(decision))
        payload = (json.dumps(dict(decision), sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.cleanup_stale_temporary()
            with self.temporary.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(self.temporary, self.path)
        except OSError as error:
            try:
                self.temporary.unlink()
            except OSError:
                pass
            raise PublicationError("ATOMIC_PUBLICATION_FAILED") from error
