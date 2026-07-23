"""Validation gate that prevents unverified patterns entering knowledge."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Iterable

from .knowledge import Knowledge
from .schema import KNOWLEDGE_STATUSES, KNOWLEDGE_VERSION


class KnowledgeValidationError(ValueError):
    pass


class KnowledgeValidator:
    def validate(self, knowledge: Knowledge, existing: Iterable[Knowledge] = (), *, validate_sequence: bool = True) -> None:
        if not knowledge.knowledge_uuid or not knowledge.pattern_uuid or not knowledge.validation_uuid:
            raise KnowledgeValidationError("REQUIRED_FIELDS")
        if knowledge.schema_version != KNOWLEDGE_VERSION:
            raise KnowledgeValidationError("INVALID_SCHEMA_VERSION")
        if knowledge.knowledge_version < 1:
            raise KnowledgeValidationError("INVALID_KNOWLEDGE_VERSION")
        if knowledge.knowledge_status not in KNOWLEDGE_STATUSES:
            raise KnowledgeValidationError("INVALID_KNOWLEDGE_STATUS")
        try:
            timestamp = datetime.fromisoformat(knowledge.created_timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise KnowledgeValidationError("INVALID_CREATED_TIMESTAMP") from exc
        if timestamp.tzinfo is None:
            raise KnowledgeValidationError("INVALID_CREATED_TIMESTAMP")
        if not isinstance(knowledge.sample_count, int) or isinstance(knowledge.sample_count, bool) or knowledge.sample_count < 0:
            raise KnowledgeValidationError("INVALID_SAMPLE_COUNT")
        for value, error in ((knowledge.verified_win_rate, "INVALID_VERIFIED_WIN_RATE"), (knowledge.average_rr, "INVALID_AVERAGE_RR")):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise KnowledgeValidationError(error)
        if not 0 <= knowledge.verified_win_rate <= 1:
            raise KnowledgeValidationError("INVALID_VERIFIED_WIN_RATE")
        for values in (knowledge.applicable_symbols, knowledge.applicable_sessions, knowledge.applicable_market_states):
            if not all(isinstance(item, str) and item for item in values):
                raise KnowledgeValidationError("INVALID_APPLICABILITY")
        if not validate_sequence:
            return

        existing_records = list(existing)

        for prior in existing_records:
            if prior.knowledge_uuid == knowledge.knowledge_uuid and prior.to_dict() != knowledge.to_dict():
                raise KnowledgeValidationError("KNOWLEDGE_IMMUTABLE")

        pattern_versions = [
            prior.knowledge_version
            for prior in existing_records
            if prior.pattern_uuid == knowledge.pattern_uuid
        ]

        if knowledge.knowledge_version in pattern_versions:
            raise KnowledgeValidationError("DUPLICATE_KNOWLEDGE_VERSION")

        expected_version = max(pattern_versions, default=0) + 1
        if knowledge.knowledge_version != expected_version:
            raise KnowledgeValidationError("INVALID_KNOWLEDGE_VERSION_SEQUENCE")
