"""Log-only operator health; it grants no runtime or trading authority."""
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class RuntimeHealth:
    startup_state: str = "STARTING"
    heartbeat_age: float | None = None
    schema_state: str = "NOT_CHECKED"
    freshness_state: str = "NOT_CHECKED"
    last_publish_timestamp: str | None = None
    runtime_version: str = "V28.PR-A"
    cycle_state: str = "NOT_STARTED"
    last_error: str | None = None
    intelligence_state: str = "NOT_EVALUATED"
    authority: str = "LOG_ONLY"

    def begin_cycle(self) -> None:
        self.heartbeat_age = None
        self.schema_state = "NOT_CHECKED"
        self.freshness_state = "NOT_CHECKED"
        self.cycle_state = "VALIDATING"
        self.last_error = None
        self.intelligence_state = "NOT_EVALUATED"

    def fail(self, code: str, *, schema: str = "UNKNOWN", freshness: str = "UNKNOWN") -> None:
        self.startup_state = "DEGRADED"
        self.schema_state = schema
        self.freshness_state = freshness
        self.cycle_state = "FAILED"
        self.last_error = code

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)
