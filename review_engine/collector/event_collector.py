import json
from datetime import datetime, timezone
from pathlib import Path
from review_engine.validation import validate_event
class EventCollector:
    """Writes only RAIP-owned files; failures are recorded, never re-raised to trading."""
    def __init__(self, root): self.root=Path(root)
    def collect(self, event):
        try:
            validate_event(event); day=datetime.fromisoformat(event["observed_at_utc"].replace("Z","+00:00")).astimezone(timezone.utc)
            path=self.root/"events"/f"{day:%Y/%m/%d}"/"events.jsonl"; path.parent.mkdir(parents=True,exist_ok=True)
            with path.open("a", encoding="utf-8") as f: f.write(json.dumps(event,sort_keys=True,separators=(",",":"))+"\n"); f.flush()
            return {"accepted":True,"path":str(path)}
        except Exception as exc:
            return self.quarantine(event, str(exc))
    def quarantine(self, record, reason):
        now=datetime.now(timezone.utc); path=self.root/"rejected"/f"{now:%Y/%m/%d}"; path.mkdir(parents=True,exist_ok=True)
        target=path/f"rejected_{int(now.timestamp() * 1_000_000_000)}.json"; target.write_text(json.dumps({"reason":reason,"record":record}, default=str, sort_keys=True),encoding="utf-8")
        return {"accepted":False,"reason":reason,"path":str(target)}
