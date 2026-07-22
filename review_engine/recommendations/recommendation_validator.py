"""Strict validation gate: invalid advisory output is never published."""
from __future__ import annotations
from collections.abc import Mapping
from .recommendation_engine import PriorityEngine, RecommendationEngine

class RecommendationValidator:
    def validate(self, package: Mapping[str, object], existing_ids: set[str] | None = None) -> tuple[bool, list[str]]:
        errors = []
        required = ("schema_version", "producer", "owner", "created_at", "insight_version", "recommendation_version", "lineage_hash", "recommendations")
        errors.extend("MISSING_" + key.upper() for key in required if key not in package)
        if package.get("schema_version") != RecommendationEngine.SCHEMA_VERSION: errors.append("SCHEMA_INCOMPATIBLE")
        if not isinstance(package.get("recommendations"), list): return False, errors + ["RECOMMENDATIONS_INVALID"]
        seen = set(existing_ids or set())
        for record in package["recommendations"]:
            if not isinstance(record, Mapping): errors.append("RECOMMENDATION_INVALID"); continue
            ident = record.get("recommendation_id")
            fields = ("recommendation_id", "priority", "supporting_insights", "supporting_knowledge", "supporting_evidence", "supporting_snapshots", "validation_status")
            errors.extend("RECOMMENDATION_MISSING_" + field.upper() for field in fields if field not in record)
            if record.get("priority") not in PriorityEngine.LEVELS: errors.append("INVALID_PRIORITY")
            if not isinstance(ident, str) or len(ident) != 64: errors.append("INVALID_RECOMMENDATION_ID")
            elif ident in seen: errors.append("DUPLICATE_RECOMMENDATION")
            seen.add(ident)
            if any(not isinstance(record.get(key), list) or not record[key] for key in fields[2:6]): errors.append("LINEAGE_INCOMPLETE")
            if record.get("validation_status") != "PENDING": errors.append("INVALID_VALIDATION_STATE")
        return not errors, sorted(set(errors))
