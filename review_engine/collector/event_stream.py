"""Append-only JSONL event stream, independent from observation and snapshot processing."""
import json, os
from pathlib import Path
from typing import Mapping
from review_engine.validation import validate_event
class EventStream:
    def __init__(self, root): self.root=Path(root)
    def publish(self, event: Mapping) -> None:
        validate_event(event)
        path=self.root / 'events' / event['occurred_at_utc'][:10].replace('-', '/') / 'events.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(event), sort_keys=True, separators=(',', ':'))+'\n'); stream.flush(); os.fsync(stream.fileno())
