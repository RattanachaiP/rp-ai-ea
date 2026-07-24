"""Atomic append-only persistence for lifecycle audit events."""
from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from .transition import LifecycleTransition


class LifecycleStorage:
    def __init__(self, root: str | Path = "learning_data") -> None:
        self.root = Path(root)

    @property
    def directory(self) -> Path:
        return self.root / "lifecycle"

    def path_for(self, transition_uuid: str) -> Path:
        try:
            canonical = str(UUID(transition_uuid))
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("INVALID_TRANSITION_UUID") from exc
        return self.directory / f"transition_{canonical}.json"

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        try:
            descriptor = os.open(directory, flags)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        except OSError:
            pass
        finally:
            os.close(descriptor)

    def write(self, transition: LifecycleTransition) -> Path:
        path = self.path_for(transition.transition_uuid)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            json.dumps(transition.to_dict(), sort_keys=True, indent=2, allow_nan=False) + "\n"
        ).encode("utf-8")
        if path.exists():
            if path.read_bytes() == payload:
                return path
            raise FileExistsError("LIFECYCLE_IMMUTABLE")
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                if path.exists() and path.read_bytes() == payload:
                    return path
                raise FileExistsError("LIFECYCLE_IMMUTABLE") from exc
            self._fsync_directory(path.parent)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        return path

    def all(self) -> list[LifecycleTransition]:
        if not self.directory.exists():
            return []
        records: list[LifecycleTransition] = []
        for path in self.directory.glob("transition_*.json"):
            try:
                records.append(
                    LifecycleTransition.from_dict(
                        json.loads(path.read_text(encoding="utf-8"))
                    )
                )
            except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
                continue
        return sorted(records, key=lambda item: item.timestamp)
