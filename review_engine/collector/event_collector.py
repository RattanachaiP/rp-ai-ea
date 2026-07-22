"""Collection and normalization only; snapshot orchestration is intentionally elsewhere."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json, os
from pathlib import Path
from typing import Callable, Mapping
from uuid import uuid4
from review_engine.collector.trade_source import TradeSource
from review_engine.config import ReviewEngineConfig
from review_engine.validation.schema_validator import SchemaValidationError, validate_event

@dataclass(frozen=True)
class CollectionResult:
    collected: int = 0
    rejected: int = 0
    disabled: bool = False

class EventCollector:
    def __init__(self, source: TradeSource, config: ReviewEngineConfig, *, clock: Callable[[], datetime] | None=None) -> None:
        self._source, self._config = source, config
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def collect(self) -> CollectionResult:
        if not self._config.enabled: return CollectionResult(disabled=True)
        collected = rejected = 0
        try: records = self._source.read_events()
        except Exception: return CollectionResult()
        for record in records:
            try:
                event=self.normalize(record); validate_event(event); self._append(event); collected += 1
            except Exception as error:
                rejected += 1; self._quarantine(record, str(error))
        return CollectionResult(collected, rejected)

    def normalize(self, record: Mapping[str, object]) -> dict[str, object]:
        if not isinstance(record, Mapping): raise SchemaValidationError("RECORD_MUST_BE_OBJECT")
        payload=record.get("payload", {})
        if not isinstance(payload, Mapping): raise SchemaValidationError("PAYLOAD_MUST_BE_OBJECT")
        now=self._iso(self._clock())
        occurred=self._normalize_timestamp(record.get("occurred_at_utc", record.get("closed_at_utc", now)))
        normal={
            "schema_version":"1.0.0", "event_id":str(record.get("event_id") or uuid4()),
            "event_type":record.get("event_type", "TRADE_CLOSED"), "occurred_at_utc":occurred, "observed_at_utc":self._normalize_timestamp(record.get("observed_at_utc", now)),
            "source_module":record.get("source_module", "unknown"), "source_version":record.get("source_version", "unknown"), "symbol":record.get("symbol", payload.get("symbol", "UNKNOWN")),
            "account_id_hash":record.get("account_id_hash"), "trade_id":record.get("trade_id", payload.get("trade_id")), "position_id":record.get("position_id", payload.get("position_id")), "series_id":record.get("series_id", payload.get("series_id")), "candidate_id":record.get("candidate_id", payload.get("candidate_id")), "sequence_id":record.get("sequence_id", payload.get("sequence_id")), "correlation_id":record.get("correlation_id", payload.get("correlation_id")),
            "payload":dict(payload),
        }
        normal["integrity"]={"payload_sha256":sha256(self._canonical(normal["payload"])).hexdigest()}
        return normal

    def _append(self, event: Mapping[str, object]) -> None:
        day=event["occurred_at_utc"][:10].split("-")
        path=self._config.review_data_root / "events" / day[0] / day[1] / day[2] / "events.jsonl"; path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("ab") as stream:
            stream.write(self._canonical(event)+b"\n"); stream.flush(); os.fsync(stream.fileno())

    def _quarantine(self, record: object, reason: str) -> None:
        if not self._config.quarantine_invalid_records: return
        now=self._clock(); path=self._config.review_data_root / "rejected" / now.strftime("%Y/%m/%d") / f"rejected_{uuid4().hex}.json"
        self._atomic(path, {"reason":reason, "record":record if isinstance(record, Mapping) else repr(record)})

    @staticmethod
    def _canonical(value: object) -> bytes: return json.dumps(value, sort_keys=True, separators=(",",":"), allow_nan=False, default=str).encode()
    @staticmethod
    def _iso(value: datetime) -> str: return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")
    def _normalize_timestamp(self, value: object) -> str:
        if not isinstance(value,str): raise SchemaValidationError("INVALID_TIMESTAMP")
        try: parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
        except ValueError as exc: raise SchemaValidationError("INVALID_TIMESTAMP") from exc
        if parsed.tzinfo is None: raise SchemaValidationError("TIMESTAMP_REQUIRES_TIMEZONE")
        return self._iso(parsed)
    def _atomic(self,path:Path,value:object)->None:
        path.parent.mkdir(parents=True,exist_ok=True); temporary=path.with_suffix(path.suffix+".tmp")
        with temporary.open("wb") as stream: stream.write(self._canonical(value)); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary,path)
