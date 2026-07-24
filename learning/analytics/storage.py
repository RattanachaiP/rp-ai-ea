"""Append-only analytics artifact publication."""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path


class AnalyticsStorage:
    def __init__(self, root="learning_data"):
        self.root = Path(root) / "analytics"
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, analytics_uuid):
        return self.root / f"report_{analytics_uuid}.json"

    @staticmethod
    def _same(path, data):
        try:
            return path.read_text(encoding="utf-8") == data
        except OSError:
            return False

    def _sync_directory_best_effort(self):
        """Persist directory metadata where the platform supports directory fsync."""
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        try:
            directory_fd = os.open(self.root, flags)
        except OSError:
            return
        try:
            os.fsync(directory_fd)
        except OSError:
            # Windows and some filesystems do not support directory fsync.
            pass
        finally:
            os.close(directory_fd)

    def write(self, report):
        """Publish without overwrite using an atomic fail-if-exists hard link.

        No persistent lock file is used, so a crashed writer cannot permanently
        block publication. The temporary file is fully flushed before linking.
        Directory metadata is synced on platforms that support it.
        """
        from .validator import validate

        validate(report)
        path = self.path_for(report.analytics_uuid)
        data = json.dumps(
            report.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        if path.exists():
            if self._same(path, data):
                return path
            raise FileExistsError("ANALYTICS_IMMUTABLE")

        fd, temporary_name = tempfile.mkstemp(
            dir=self.root,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if self._same(path, data):
                    return path
                raise FileExistsError("ANALYTICS_IMMUTABLE")
            self._sync_directory_best_effort()
            return path
        finally:
            temporary.unlink(missing_ok=True)
