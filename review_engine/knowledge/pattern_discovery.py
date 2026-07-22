"""Read-only aggregation of V2 evidence into deterministic knowledge records."""
from __future__ import annotations

from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
from pathlib import Path
from typing import Callable, Iterable, Mapping

from .pattern_repository import PatternRepository


PATTERNS = ("TREND", "RANGE", "BREAKOUT", "PULLBACK", "CONTINUATION", "REVERSAL", "NEWS", "UNKNOWN")
SESSIONS = ("ASIA", "LONDON", "NEW_YORK", "OVERLAP", "UNKNOWN")
MARKET_STATES = ("TREND", "RANGE", "TRANSITION", "VOLATILE", "NEWS")


class PatternDiscoveryEngine:
    """Pure evidence aggregator; it has no runtime or trading-layer imports."""

    SCHEMA_VERSION = "3.0.0"
    PRODUCER = "RAIP Pattern Discovery Engine"
    OWNER = "RAIP Knowledge Layer"

    def __init__(self, *, clock: Callable[[], datetime] | None = None):
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def generate(self, evidence: Iterable[Mapping[str, object]]) -> dict[str, object]:
        items = sorted((dict(item) for item in evidence), key=lambda item: str(item.get("evidence_id", "")))
        source_ids = [str(item.get("evidence_id", "")) for item in items]
        source_versions = sorted({str(item.get("schema_version", "UNKNOWN")) for item in items})
        statistics = {
            "pattern_statistics": {key: self._pattern_metrics(self._select(items, "classification", key)) for key in PATTERNS},
            "session_statistics": {key: self._session_metrics(self._select_by(self._session, items, key)) for key in SESSIONS},
            "market_state_statistics": {key: self._market_metrics(self._select_by(self._market_state, items, key)) for key in MARKET_STATES},
            "confidence_calibration": self._calibration(items),
        }
        generated_from = {"evidence_count": len(items), "evidence_ids": source_ids, "evidence_digest": self._digest(source_ids)}
        version = self._digest({"source": generated_from, "statistics": statistics})
        return {
            "schema_version": self.SCHEMA_VERSION, "producer": self.PRODUCER, "owner": self.OWNER,
            "created_at": self._iso(self.clock()), "source_schema_version": source_versions,
            "generated_from": generated_from, "pattern_repository_version": version, "statistics": statistics,
        }

    def _pattern_metrics(self, items: list[Mapping[str, object]]) -> dict[str, object]:
        base = self._base(items)
        profits = [self._profit(item) for item in items]
        base.update({
            "loss_rate": self._rate(sum(self._outcome(item) == "LOSS" for item in items), len(items)),
            "average_profit": self._average([profit for profit in profits if profit > 0]),
            "average_loss": self._average([profit for profit in profits if profit < 0]),
            "average_duration": self._average([self._duration(item) for item in items]),
            "average_confidence": self._average([self._confidence(item) for item in items]),
        })
        return base

    def _session_metrics(self, items: list[Mapping[str, object]]) -> dict[str, object]:
        base = self._base(items)
        profits = [self._profit(item) for item in items]
        gains, losses = sum(value for value in profits if value > 0), abs(sum(value for value in profits if value < 0))
        base.update({"profit_factor": round(gains / losses, 6) if losses else (None if not gains else None), "average_drawdown": self._average([self._drawdown(item) for item in items])})
        return base

    def _market_metrics(self, items: list[Mapping[str, object]]) -> dict[str, object]:
        return {"win_rate": self._rate(sum(self._outcome(item) == "WIN" for item in items), len(items)), "average_rr": self._average([self._number(item.get("rr")) for item in items]), "confidence_distribution": self._confidence_distribution(items)}

    def _base(self, items: list[Mapping[str, object]]) -> dict[str, object]:
        return {"trade_count": len(items), "win_rate": self._rate(sum(self._outcome(item) == "WIN" for item in items), len(items)), "average_rr": self._average([self._number(item.get("rr")) for item in items])}

    def _calibration(self, items: list[Mapping[str, object]]) -> dict[str, dict[str, object]]:
        result = {}
        for lower in range(50, 100, 10):
            label, upper = f"{lower}-{lower + 10}%", lower + 10
            selected = [item for item in items if lower <= self._confidence(item) * 100 < upper or (upper == 100 and self._confidence(item) * 100 == 100)]
            result[label] = {"sample_size": len(selected), "actual_win_rate": self._rate(sum(self._outcome(item) == "WIN" for item in selected), len(selected)), "average_rr": self._average([self._number(item.get("rr")) for item in selected])}
        return result

    def _confidence_distribution(self, items: list[Mapping[str, object]]) -> dict[str, int]:
        return dict(sorted(Counter(self._confidence_bucket(self._confidence(item)) for item in items).items()))

    @staticmethod
    def _select(items, key, value): return [item for item in items if str(item.get(key, "UNKNOWN")).upper() == value]
    @staticmethod
    def _select_by(selector, items, value): return [item for item in items if selector(item) == value]
    @staticmethod
    def _outcome(item): return str(item.get("win_loss", item.get("result", "BREAKEVEN"))).upper()
    @staticmethod
    def _number(value):
        try: return float(value) if value is not None else 0.0
        except (TypeError, ValueError): return 0.0
    def _profit(self, item):
        stats = item.get("statistics", {}) if isinstance(item.get("statistics"), Mapping) else {}
        return self._number(item.get("net_profit", stats.get("net_profit", stats.get("profit", 0))))
    def _duration(self, item):
        stats = item.get("statistics", {}) if isinstance(item.get("statistics"), Mapping) else {}
        return self._number(item.get("duration", item.get("duration_seconds", stats.get("duration", stats.get("duration_seconds", 0)))))
    def _drawdown(self, item):
        stats = item.get("statistics", {}) if isinstance(item.get("statistics"), Mapping) else {}
        return abs(self._number(item.get("drawdown", item.get("mae", stats.get("drawdown", stats.get("mae", stats.get("mae_points", 0)))))))
    def _confidence(self, item):
        value = self._number(item.get("confidence")); return value / 100 if value > 1 else max(0.0, value)
    @staticmethod
    def _session(item):
        return str(item.get("session", item.get("trading_session", "UNKNOWN"))).upper().replace(" ", "_").replace("-", "_")
    @staticmethod
    def _market_state(item): return str(item.get("market_state", "UNKNOWN")).upper().replace(" ", "_").replace("-", "_")
    @staticmethod
    def _confidence_bucket(value): return f"{min(90, max(0, int(value * 100) // 10 * 10))}-{min(100, max(0, int(value * 100) // 10 * 10 + 10))}%"
    @staticmethod
    def _rate(value, count): return round(value / count, 6) if count else None
    @staticmethod
    def _average(values): return round(sum(values) / len(values), 6) if values else None
    @staticmethod
    def _digest(value): return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    @staticmethod
    def _iso(value): return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class KnowledgeCoordinator:
    """Asynchronous, failure-isolated processor for evidence already on disk."""
    def __init__(self, evidence_root: Path | str, repository: PatternRepository | None = None, engine: PatternDiscoveryEngine | None = None):
        self.evidence_root, self.repository, self.engine = Path(evidence_root), repository or PatternRepository(evidence_root), engine or PatternDiscoveryEngine()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="raip-knowledge")
        self.log = logging.getLogger(__name__)
    def process_available(self) -> Path:
        records = []
        for path in sorted((self.evidence_root / "evidence").glob("evidence_*.json")) if (self.evidence_root / "evidence").exists() else []:
            try: records.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError) as exc: self.log.error("knowledge evidence read failed: %s", exc)
        return self.repository.save(self.engine.generate(records))
    def process_async(self) -> Future[Path]: return self._executor.submit(self.process_available)
    def shutdown(self): self._executor.shutdown(wait=True)
