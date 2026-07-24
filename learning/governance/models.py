"""Immutable, serialisable metadata describing a Knowledge record's governance."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from .schema import GOVERNANCE_SCHEMA_VERSION


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class KnowledgeGovernance:
    knowledge_uuid: str
    pattern_uuid: str
    validation_uuid: str
    analytics_uuid: str
    source_baseline_commit: str
    rule_version: str
    analytics_version: str
    current_lifecycle_state: str
    lineage_reference: str
    production_eligible: bool
    promotion_timestamp: str | None = None
    retirement_timestamp: str | None = None
    schema_version: str = GOVERNANCE_SCHEMA_VERSION
    record_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_uuid": self.knowledge_uuid,
            "pattern_uuid": self.pattern_uuid,
            "validation_uuid": self.validation_uuid,
            "analytics_uuid": self.analytics_uuid,
            "source_baseline_commit": self.source_baseline_commit,
            "schema_version": self.schema_version,
            "rule_version": self.rule_version,
            "analytics_version": self.analytics_version,
            "promotion_timestamp": self.promotion_timestamp,
            "retirement_timestamp": self.retirement_timestamp,
            "current_lifecycle_state": self.current_lifecycle_state,
            "lineage_reference": self.lineage_reference,
            "production_eligible": self.production_eligible,
            "record_version": self.record_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "KnowledgeGovernance":
        return cls(
            knowledge_uuid=str(value["knowledge_uuid"]), pattern_uuid=str(value["pattern_uuid"]),
            validation_uuid=str(value["validation_uuid"]), analytics_uuid=str(value["analytics_uuid"]),
            source_baseline_commit=str(value["source_baseline_commit"]), rule_version=str(value["rule_version"]),
            analytics_version=str(value["analytics_version"]),
            current_lifecycle_state=str(value["current_lifecycle_state"]),
            lineage_reference=str(value["lineage_reference"]), production_eligible=value["production_eligible"],
            promotion_timestamp=value.get("promotion_timestamp"), retirement_timestamp=value.get("retirement_timestamp"),
            schema_version=str(value.get("schema_version", GOVERNANCE_SCHEMA_VERSION)),
            record_version=int(value.get("record_version", 1)),
        )
