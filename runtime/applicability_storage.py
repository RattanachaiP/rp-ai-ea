"""Durable append-only persistence for Runtime applicability reports."""
from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from runtime.knowledge_applicability import ApplicabilityReport


class ApplicabilityReportRepository:
    def __init__(self, root: str | Path = "learning_data") -> None:
        self.root = Path(root)

    def append(self, report: ApplicabilityReport) -> Path:
        if not isinstance(report, ApplicabilityReport):
            raise TypeError("APPLICABILITY_REPORT_REQUIRED")
        directory = self.root / "applicability_reports"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"report_{report.report_uuid}.json"
        data = (json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
        if path.exists():
            if path.read_bytes() != data:
                raise FileExistsError("APPLICABILITY_REPORT_APPEND_ONLY")
            return path
        tmp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with tmp.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(tmp, path)
            except FileExistsError:
                if path.read_bytes() != data:
                    raise FileExistsError("APPLICABILITY_REPORT_APPEND_ONLY")
            self._fsync_directory(directory)
        finally:
            tmp.unlink(missing_ok=True)
        return path

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        if os.name == "nt":
            return
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
