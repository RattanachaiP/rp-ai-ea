"""Operator-visible health for the V28 process; never trading authority."""
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

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)
