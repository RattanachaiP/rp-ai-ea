"""Append-only canonical JSON repository for PR175 reports."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile

from .models import PatternMiningReport

_UUID_NAME = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class PatternMiningRepository:
    def __init__(self, root: str | Path = "learning_data/pattern_mining"):
        self.root = Path(root)

    def path_for(self, report_uuid: str) -> Path:
        if not isinstance(report_uuid, str) or not _UUID_NAME.fullmatch(report_uuid):
            raise ValueError("INVALID_REPORT_FILENAME")
        return self.root / f"{report_uuid}.json"

    def save(self, report: PatternMiningReport) -> Path:
        if not isinstance(report, PatternMiningReport):
            raise TypeError("INVALID_PATTERN_MINING_REPORT")
        path = self.path_for(report.report_uuid)
        payload = json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        self.root.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".pattern-mining-", dir=self.root)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != payload:
                    raise FileExistsError("PATTERN_MINING_REPORT_COLLISION") from None
        except BaseException:
            raise
        finally:
            temporary.unlink(missing_ok=True)
        return path
