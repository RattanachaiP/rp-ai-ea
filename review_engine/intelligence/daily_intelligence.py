"""Read-only daily aggregation of immutable evidence."""
from __future__ import annotations
from datetime import datetime, timezone
import json, os
from pathlib import Path
from typing import Callable, Iterable, Mapping
class DailyIntelligenceGenerator:
 def __init__(self, *, clock: Callable[[], datetime] | None = None): self.clock = clock or (lambda: datetime.now(timezone.utc))
 def generate(self, evidence: Iterable[Mapping[str, object]], date_utc: str, processing_errors: int = 0) -> dict[str, object]:
  items = sorted(evidence, key=lambda item: str(item.get("evidence_id", ""))); count = len(items)
  wins = sum(item.get("win_loss") == "WIN" for item in items)
  def number(item, key, nested=None):
   value = item.get(key) if nested is None else (item.get(nested, {}) if isinstance(item.get(nested), Mapping) else {}).get(key)
   try: return float(value) if value is not None else 0.0
   except (TypeError, ValueError): return 0.0
  distribution = {label: sum(item.get("classification") == label for item in items) for label in sorted({str(item.get("classification", "UNKNOWN")) for item in items})}
  return {"schema_version": "2.0.0", "producer": "RAIP Review & Evidence Engine", "owner": "RAIP Evidence Layer", "created_at": self._iso(self.clock()), "evidence_id": f"daily:{date_utc}", "date_utc": date_utc, "trade_count": count, "win_rate": round(wins / count, 6) if count else None, "average_rr": round(sum(number(item, "rr") for item in items) / count, 6) if count else None, "average_confidence": round(sum(number(item, "confidence") for item in items) / count, 6) if count else None, "classification_distribution": distribution, "entry_score": self._average(items, "entry_timing"), "exit_score": self._average(items, "exit_timing"), "evidence_generated": count, "processing_errors": int(processing_errors), "evidence_ids": [item.get("evidence_id") for item in items]}
 def _average(self, items, key):
  if not items: return None
  values = []
  for item in items:
   try: values.append(float((item.get("statistics", {}) if isinstance(item.get("statistics"), Mapping) else {}).get(key, 0)))
   except (TypeError, ValueError): values.append(0.0)
  return round(sum(values) / len(values), 6)
 @staticmethod
 def _iso(value): return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
class DailyIntelligenceRepository:
 def __init__(self, root: Path | str): self.root = Path(root)
 def load_evidence(self):
  records = []
  for path in sorted((self.root / "evidence").glob("evidence_*.json")) if (self.root / "evidence").exists() else []:
   try: records.append(json.loads(path.read_text(encoding="utf-8")))
   except (OSError, json.JSONDecodeError): continue
  return records
 def write(self, date_utc: str, report: Mapping[str, object]) -> Path:
  path = self.root / "intelligence" / date_utc.replace("-", "/") / "daily_intelligence.json"; path.parent.mkdir(parents=True, exist_ok=True); temp = path.with_suffix(".json.tmp")
  with temp.open("wb") as f: f.write((json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()); f.flush(); os.fsync(f.fileno())
  os.replace(temp, path); return path
