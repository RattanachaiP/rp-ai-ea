"""Atomic append-only persistence for immutable promotion journal records."""
from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from .models import PromotionRecord

_STATE_ORDER = {"PREPARED": 0, "COMMITTED": 1, "FAILED": 1, "IN_DOUBT": 1}


class PromotionRecordStorage:
    def __init__(self, root="learning_data") -> None:
        self.root = Path(root)

    @property
    def directory(self) -> Path:
        return self.root / "promotion_records"

    def path_for(self, record_uuid: str) -> Path:
        try:
            canonical = str(UUID(record_uuid))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("INVALID_PROMOTION_RECORD_UUID") from exc
        return self.directory / f"record_{canonical}.json"

    def write(self, record: PromotionRecord) -> Path:
        path = self.path_for(record.record_uuid)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = (json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
        if path.exists():
            if path.read_bytes() == data:
                return path
            raise FileExistsError("PROMOTION_RECORD_IMMUTABLE")
        tmp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with tmp.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(tmp, path)
            except FileExistsError as exc:
                if path.exists() and path.read_bytes() == data:
                    return path
                raise FileExistsError("PROMOTION_RECORD_IMMUTABLE") from exc
        finally:
            tmp.unlink(missing_ok=True)
        return path

    def all(self) -> tuple[PromotionRecord, ...]:
        records: list[PromotionRecord] = []
        if not self.directory.exists():
            return ()
        for path in sorted(self.directory.glob("record_*.json")):
            try:
                records.append(PromotionRecord(**json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                continue
        return tuple(sorted(records, key=lambda item: (
            item.timestamp,
            item.decision_uuid,
            _STATE_ORDER[item.status],
            item.record_uuid,
        )))

    def for_decision(self, decision_uuid: str) -> tuple[PromotionRecord, ...]:
        return tuple(record for record in self.all() if record.decision_uuid == decision_uuid)

    def committed(self, decision_uuid: str) -> PromotionRecord | None:
        return next((record for record in reversed(self.for_decision(decision_uuid)) if record.status == "COMMITTED"), None)
