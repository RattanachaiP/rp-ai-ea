"""Crash-safe, append-only analytics artifact publication."""
from __future__ import annotations
import json
import os
import tempfile
import time
from pathlib import Path

class AnalyticsStorage:
    def __init__(self, root="learning_data"):
        self.root = Path(root) / "analytics"
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, analytics_uuid):
        return self.root / f"report_{analytics_uuid}.json"

    @staticmethod
    def _same(path, data):
        try: return path.read_text(encoding="utf-8") == data
        except OSError: return False

    def write(self, report):
        """Publish a fully-fsynced temp artifact with an exclusive lock.

        The lock prevents ``os.replace`` from overwriting an artifact written by
        another AnalyticsStorage caller.  A stale lock without a final artifact
        is safely recovered; orphan temporary files are deliberately ignored.
        """
        path = self.path_for(report.analytics_uuid)
        lock = self.root / f".{path.name}.lock"
        data = json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        if path.exists():
            if self._same(path, data): return path
            raise FileExistsError("ANALYTICS_IMMUTABLE")
        try:
            lock_fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            # Wait for an in-flight publisher. Never remove a fresh lock: doing
            # so would permit concurrent overwrite. A lock older than 30s with
            # no final artifact is an interrupted process and may be recovered.
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline and not path.exists():
                time.sleep(0.01)
            if path.exists():
                if self._same(path, data): return path
                raise FileExistsError("ANALYTICS_IMMUTABLE")
            if time.time() - lock.stat().st_mtime > 30.0:
                lock.unlink(missing_ok=True)
                return self.write(report)
            raise TimeoutError("ANALYTICS_PUBLICATION_IN_PROGRESS")
        os.close(lock_fd)
        temporary = None
        try:
            if path.exists():
                if self._same(path, data): return path
                raise FileExistsError("ANALYTICS_IMMUTABLE")
            fd, temporary_name = tempfile.mkstemp(dir=self.root, prefix=f".{path.name}.", suffix=".tmp")
            temporary = Path(temporary_name)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(data); handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary, path)
            temporary = None
            return path
        finally:
            if temporary is not None: temporary.unlink(missing_ok=True)
            lock.unlink(missing_ok=True)
