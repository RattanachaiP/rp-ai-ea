"""Append-only on-disk repository for RAIP-owned review artifacts."""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

class SnapshotConflictError(RuntimeError): pass

def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

class SnapshotRepository:
    def __init__(self, root: Path | str): self.root = Path(root).expanduser().resolve()
    def _dated(self, category: str, when: str) -> Path:
        day = datetime.fromisoformat(when.replace("Z", "+00:00")); return self.root / category / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}"
    def _safe_id(self, identifier: str) -> str:
        if not identifier or Path(identifier).name != identifier or identifier in {".", ".."}: raise ValueError("unsafe identifier")
        return identifier
    def atomic_write(self, path: Path, value: Mapping[str, Any], overwrite: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not overwrite: raise FileExistsError(path)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            with temporary.open("wb") as handle:
                handle.write(canonical_json(value)); handle.flush(); os.fsync(handle.fileno())
            if not overwrite and path.exists(): raise FileExistsError(path)
            os.replace(temporary, path)
        finally:
            if temporary.exists(): temporary.unlink(missing_ok=True)
    def append_event(self, event: Mapping[str, Any]) -> Path:
        path = self._dated("events", event["occurred_at_utc"]) / "events.jsonl"; path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing_ids = {json.loads(line).get("event_id") for line in path.read_text("utf-8").splitlines()}
            if event["event_id"] in existing_ids: return path
        with path.open("ab") as handle:
            handle.write(canonical_json(event) + b"\n"); handle.flush(); os.fsync(handle.fileno())
        return path
    def quarantine(self, raw: Any, reason: list[str], observed_at: str | None = None) -> Path:
        when = observed_at or utc_now(); digest = sha256(repr(raw).encode()).hexdigest(); path = self._dated("rejected", when) / f"rejected_{digest}.json"
        self.atomic_write(path, {"reason": reason, "observed_at_utc": when, "raw": raw if isinstance(raw, (dict, list, str, int, float, bool, type(None))) else repr(raw)})
        return path
    def store_snapshot(self, snapshot: Mapping[str, Any]) -> tuple[Path, bool]:
        trade_id = self._safe_id(snapshot["trade_identity"]["trade_id"]); path = self._dated("snapshots", snapshot["timeline"]["closed_at_utc"]) / f"trade_{trade_id}.json"
        if path.exists():
            if canonical_json(json.loads(path.read_text("utf-8"))) == canonical_json(snapshot): return path, False
            raise SnapshotConflictError(f"conflicting immutable snapshot for {trade_id}")
        self.atomic_write(path, snapshot); return path, True
    def save_collector_state(self, state: Mapping[str, Any]) -> Path:
        path = self.root / "runtime" / "collector_state.json"
        self.atomic_write(path, state, overwrite=True)
        return path
    def load_collector_state(self) -> dict[str, Any]:
        path = self.root / "runtime" / "collector_state.json"
        return json.loads(path.read_text("utf-8")) if path.exists() else {}
    def load_events_for_trade(self, event: Mapping[str, Any]) -> list[dict[str, Any]]:
        path = self._dated("events", event["occurred_at_utc"]) / "events.jsonl"
        if not path.exists(): return []
        return [row for row in (json.loads(line) for line in path.read_text("utf-8").splitlines()) if row.get("trade_id") == event.get("trade_id")]
    def load_snapshots(self, date_utc: str) -> list[dict[str, Any]]:
        path = self.root / "snapshots" / date_utc.replace("-", "/")
        return [json.loads(item.read_text("utf-8")) for item in sorted(path.glob("trade_*.json"))] if path.exists() else []
    def write_daily_review(self, date_utc: str, report: Mapping[str, Any]) -> Path:
        path = self.root / "daily" / date_utc.replace("-", "/") / "daily_review.json"; self.atomic_write(path, report, overwrite=True); return path
