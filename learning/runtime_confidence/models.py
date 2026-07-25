"""Immutable, standalone-auditable PR182 advisory confidence artifacts."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from math import isfinite

from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid
from learning.common.immutable import freeze, thaw
from learning.runtime_selection import RuntimeKnowledgeSelection

from .identity import digest, report_uuid, snapshot_uuid, confidence_uuid
from .policy import DEFAULT_BANDS, DEFAULT_REASON_ORDER, DIMENSIONS

CONFIDENCE_STATES = (
    "REJECTED",
    "INSUFFICIENT_CONFIDENCE_EVIDENCE",
    "CONFIDENCE_EVALUATED",
)
DIMENSION_STATES = ("SATISFIED", "PARTIAL", "UNSATISFIED")
AUTHORITY_SCOPE = "ADVISORY_CONFIDENCE_ONLY"
SOURCE_ARTIFACT_TYPES = (
    "ELIGIBILITY_RECORD",
    "ELIGIBILITY_REPORT",
    "ELIGIBILITY_SNAPSHOT",
)
CONFIDENCE_PARTITION_FIELDS = (
    "confidence_policy_uuid",
    "confidence_policy_digest",
    "confidence_policy_version",
    "confidence_engine_version",
)
SOURCE_PARTITION_FIELDS = (
    "selector_version",
    "selection_policy_uuid",
    "selection_policy_digest",
    "selection_policy_version",
    "source_runtime_engine_version",
    "source_runtime_packaging_policy_uuid",
    "source_runtime_packaging_policy_digest",
    "source_runtime_packaging_policy_version",
    "source_registry_engine_version",
    "source_registry_admission_policy_uuid",
    "source_registry_admission_policy_digest",
    "source_registry_admission_policy_version",
    "source_promotion_engine_version",
    "source_promotion_policy_uuid",
    "source_promotion_policy_digest",
    "source_promotion_policy_version",
    "source_validator_version",
    "source_validation_policy_version",
    "source_validation_config_digest",
    "source_mining_engine_version",
    "source_mining_policy_uuid",
    "source_mining_policy_version",
    "source_mining_config_digest",
)
PARTITION_FIELDS = CONFIDENCE_PARTITION_FIELDS + SOURCE_PARTITION_FIELDS


def _valid_reasons(value):
    return (
        isinstance(value, tuple)
        and bool(value)
        and all(isinstance(item, str) and item for item in value)
        and len(set(value)) == len(value)
    )


def _rounded(value, precision):
    quantum = Decimal(1).scaleb(-precision)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_EVEN))


def confidence_band(score, thresholds=DEFAULT_BANDS):
    band = thresholds[0][0]
    for name, lower_bound in thresholds:
        if score >= lower_bound:
            band = name
    return band


@dataclass(frozen=True)
class ConfidenceDimensionResult:
    dimension: str
    state: str
    raw_value: str
    normalized_score: float
    weight: float
    weighted_contribution: float
    reasons: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, "reasons", tuple(self.reasons))
        if (
            self.dimension not in DIMENSIONS
            or self.state not in DIMENSION_STATES
            or not isinstance(self.raw_value, str)
            or not self.raw_value
            or type(self.normalized_score) is not float
            or not isfinite(self.normalized_score)
            or not 0.0 <= self.normalized_score <= 1.0
            or type(self.weight) is not float
            or not isfinite(self.weight)
            or not 0.0 <= self.weight <= 1.0
            or type(self.weighted_contribution) is not float
            or not isfinite(self.weighted_contribution)
            or self.weighted_contribution
            != _rounded(self.normalized_score * self.weight, 12)
            or not _valid_reasons(self.reasons)
        ):
            raise ValueError("INVALID_CONFIDENCE_EVIDENCE")

    def to_dict(self):
        return {
            "dimension": self.dimension,
            "state": self.state,
            "raw_value": self.raw_value,
            "normalized_score": self.normalized_score,
            "weight": self.weight,
            "weighted_contribution": self.weighted_contribution,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ConfidenceRecord:
    confidence_uuid: str
    confidence_digest: str
    confidence_state: str
    confidence_score: float
    confidence_band: str
    confidence_reasons: tuple[str, ...]
    confidence_dimension_results: tuple[ConfidenceDimensionResult, ...]
    source_eligibility_uuid: str
    source_eligibility_digest: str
    source_eligibility_state: str
    source_eligibility_reasons: tuple[str, ...]
    source_eligibility_scope: str
    source_eligibility_snapshot_uuid: str
    source_eligibility_snapshot_digest: str
    source_eligibility_repository_digest: str
    source_selection_policy_uuid: str
    source_selection_policy_digest: str
    source_selection_policy_version: str
    source_selector_version: str
    source_runtime_package_uuid: str
    source_runtime_package_digest: str
    source_runtime_snapshot_uuid: str
    source_runtime_snapshot_digest: str
    source_runtime_repository_digest: str
    source_runtime_engine_version: str
    source_runtime_packaging_policy_uuid: str
    source_runtime_packaging_policy_digest: str
    source_runtime_packaging_policy_version: str
    source_registry_engine_version: str
    source_registry_admission_policy_uuid: str
    source_registry_admission_policy_digest: str
    source_registry_admission_policy_version: str
    source_promotion_engine_version: str
    source_promotion_policy_uuid: str
    source_promotion_policy_digest: str
    source_promotion_policy_version: str
    source_validator_version: str
    source_validation_policy_version: str
    source_validation_config_digest: str
    source_mining_engine_version: str
    source_mining_policy_uuid: str
    source_mining_policy_version: str
    source_mining_config_digest: str
    source_registry_uuid: str
    source_registry_digest: str
    source_promotion_uuid: str
    source_promotion_digest: str
    source_validation_uuid: str
    source_validation_digest: str
    source_memory_uuid: str
    source_memory_digest: str
    source_pattern_uuid: str
    source_pattern_hash: str
    knowledge_uuid: str
    knowledge_version: str
    memory_version: str
    memory_state: str
    source_report_uuid: str
    source_policy_uuid: str
    source_policy_version: str
    source_attribution_uuid: str
    source_digest: str
    replay_digest: str
    evidence_envelope_uuid: str
    evidence_envelope_digest: str
    source_engine_version: str
    mining_config_digest: str
    outcome_contract: tuple[str, str]
    source_validation_statistics: Mapping
    source_validated_at: str
    source_validation_thresholds: Mapping
    promotion_policy_thresholds: Mapping
    threshold_monotonicity_result: str
    source_promotion_created_at: str
    source_registry_recorded_at: str
    source_runtime_package_state: str
    source_runtime_package_reasons: tuple[str, ...]
    source_registry_state: str
    source_registry_reasons: tuple[str, ...]
    source_validation_state: str
    source_validation_reasons: tuple[str, ...]
    source_promotion_state: str
    source_promotion_reasons: tuple[str, ...]
    selector_version: str
    selection_policy_uuid: str
    selection_policy_digest: str
    selection_policy_version: str
    confidence_policy_uuid: str
    confidence_policy_digest: str
    confidence_policy_version: str
    confidence_engine_version: str
    score_precision: int
    confidence_band_thresholds: tuple[tuple[str, float], ...]
    reason_ordering_rules: tuple[str, ...]
    created_at: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        reason_fields = (
            "confidence_reasons",
            "source_eligibility_reasons",
            "source_runtime_package_reasons",
            "source_registry_reasons",
            "source_validation_reasons",
            "source_promotion_reasons",
        )
        for name in reason_fields:
            object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(self, "outcome_contract", tuple(self.outcome_contract))
        for name in (
            "source_validation_statistics",
            "source_validation_thresholds",
            "promotion_policy_thresholds",
        ):
            object.__setattr__(self, name, freeze(thaw(getattr(self, name))))
        dimensions = tuple(self.confidence_dimension_results)
        thresholds = tuple(tuple(item) for item in self.confidence_band_thresholds)
        reason_order = tuple(self.reason_ordering_rules)
        object.__setattr__(self, "confidence_dimension_results", dimensions)
        object.__setattr__(self, "confidence_band_thresholds", thresholds)
        object.__setattr__(self, "reason_ordering_rules", reason_order)

        uuid_fields = (
            "confidence_uuid",
            "source_eligibility_uuid",
            "source_eligibility_snapshot_uuid",
            "source_selection_policy_uuid",
            "source_runtime_package_uuid",
            "source_runtime_snapshot_uuid",
            "source_runtime_packaging_policy_uuid",
            "source_registry_admission_policy_uuid",
            "source_promotion_policy_uuid",
            "source_registry_uuid",
            "source_promotion_uuid",
            "source_validation_uuid",
            "source_memory_uuid",
            "source_pattern_uuid",
            "knowledge_uuid",
            "selection_policy_uuid",
            "confidence_policy_uuid",
        )
        digest_fields = (
            "confidence_digest",
            "source_eligibility_digest",
            "source_eligibility_snapshot_digest",
            "source_eligibility_repository_digest",
            "source_selection_policy_digest",
            "source_runtime_package_digest",
            "source_runtime_snapshot_digest",
            "source_runtime_repository_digest",
            "source_runtime_packaging_policy_digest",
            "source_registry_admission_policy_digest",
            "source_promotion_policy_digest",
            "source_registry_digest",
            "source_promotion_digest",
            "source_validation_digest",
            "source_memory_digest",
            "source_pattern_hash",
            "selection_policy_digest",
            "confidence_policy_digest",
        )
        expected_score = _rounded(
            sum(item.weighted_contribution for item in dimensions), self.score_precision
        )
        ordered_reasons = tuple(
            reason for reason in reason_order if reason in set(self.confidence_reasons)
        )
        if (
            not all(valid_uuid(getattr(self, name)) for name in uuid_fields)
            or not all(valid_digest(getattr(self, name)) for name in digest_fields)
            or not all(_valid_reasons(getattr(self, name)) for name in reason_fields)
            or self.confidence_state not in CONFIDENCE_STATES
            or type(self.confidence_score) is not float
            or not isfinite(self.confidence_score)
            or not 0.0 <= self.confidence_score <= 1.0
            or self.confidence_score != expected_score
            or tuple(item.dimension for item in dimensions) != DIMENSIONS
            or len({item.dimension for item in dimensions}) != len(dimensions)
            or self.confidence_band
            != confidence_band(self.confidence_score, thresholds)
            or self.confidence_reasons != ordered_reasons
            or not self.knowledge_version
            or not all(
                getattr(self, name)
                for name in PARTITION_FIELDS
                if name.endswith("version")
            )
            or self.source_selection_policy_uuid != self.selection_policy_uuid
            or self.source_selection_policy_digest != self.selection_policy_digest
            or self.source_selection_policy_version != self.selection_policy_version
            or self.source_selector_version != self.selector_version
            or self.source_mining_engine_version != self.source_engine_version
            or self.source_mining_policy_uuid != self.source_policy_uuid
            or self.source_mining_policy_version != self.source_policy_version
            or self.source_mining_config_digest != self.mining_config_digest
            or self.source_eligibility_scope != "ADVISORY_ELIGIBILITY_ONLY"
            or self.authority_scope != AUTHORITY_SCOPE
            or self.advisory_only is not True
            or not valid_timestamp(self.created_at)
            or confidence_uuid(self.identity_payload()) != self.confidence_uuid
            or digest(self.digest_payload()) != self.confidence_digest
        ):
            raise ValueError("INVALID_CONFIDENCE_RECORD")
        try:
            RuntimeKnowledgeSelection(**self.eligibility_record_dict())
        except (TypeError, ValueError) as exc:
            raise ValueError("INVALID_CONFIDENCE_PROVENANCE") from exc

    def eligibility_record_dict(self):
        direct = {
            "selection_uuid": self.source_eligibility_uuid,
            "selection_digest": self.source_eligibility_digest,
            "selection_state": self.source_eligibility_state,
            "selection_reasons": self.source_eligibility_reasons,
            "selection_scope": self.source_eligibility_scope,
            "selection_policy_uuid": self.source_selection_policy_uuid,
            "selection_policy_digest": self.source_selection_policy_digest,
            "selection_policy_version": self.source_selection_policy_version,
            "selector_version": self.source_selector_version,
            "created_at": self.created_at,
            "advisory_only": True,
        }
        for name in RuntimeKnowledgeSelection.__dataclass_fields__:
            if name not in direct:
                direct[name] = thaw(getattr(self, name))
        return direct

    def identity_payload(self):
        return {
            name: (
                [item.to_dict() for item in self.confidence_dimension_results]
                if name == "confidence_dimension_results"
                else (
                    [list(item) for item in self.confidence_band_thresholds]
                    if name == "confidence_band_thresholds"
                    else (
                        list(self.reason_ordering_rules)
                        if name == "reason_ordering_rules"
                        else (
                            list(getattr(self, name))
                            if name.endswith("reasons")
                            else thaw(getattr(self, name))
                        )
                    )
                )
            )
            for name in self.__dataclass_fields__
            if name not in {"confidence_uuid", "confidence_digest"}
        }

    def digest_payload(self):
        return {"confidence_uuid": self.confidence_uuid, **self.identity_payload()}

    def to_dict(self):
        return {
            "confidence_uuid": self.confidence_uuid,
            "confidence_digest": self.confidence_digest,
            **self.identity_payload(),
        }

    @classmethod
    def create(cls, **values):
        values = dict(values)
        for name in (
            "confidence_reasons",
            "source_eligibility_reasons",
            "source_runtime_package_reasons",
            "source_registry_reasons",
            "source_validation_reasons",
            "source_promotion_reasons",
        ):
            values[name] = tuple(values[name])
        values["confidence_dimension_results"] = tuple(
            values["confidence_dimension_results"]
        )
        values["confidence_band_thresholds"] = tuple(
            tuple(item) for item in values["confidence_band_thresholds"]
        )
        values["reason_ordering_rules"] = tuple(values["reason_ordering_rules"])
        values["outcome_contract"] = tuple(values["outcome_contract"])
        for name in (
            "source_validation_statistics",
            "source_validation_thresholds",
            "promotion_policy_thresholds",
        ):
            values[name] = thaw(values[name])
        payload = cls._serialize_values(values)
        identity = confidence_uuid(payload)
        return cls(
            confidence_uuid=identity,
            confidence_digest=digest({"confidence_uuid": identity, **payload}),
            **values,
        )

    @staticmethod
    def _serialize_values(values):
        output = dict(values)
        output["confidence_dimension_results"] = [
            item.to_dict() for item in values["confidence_dimension_results"]
        ]
        output["confidence_band_thresholds"] = [
            list(item) for item in values["confidence_band_thresholds"]
        ]
        output["reason_ordering_rules"] = list(values["reason_ordering_rules"])
        for name in tuple(output):
            if name.endswith("reasons"):
                output[name] = list(output[name])
        return output


@dataclass(frozen=True)
class ConfidenceSnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    source_artifact_type: str
    source_artifact_uuid: str
    source_artifact_digest: str
    source_eligibility_snapshot_uuid: str
    source_eligibility_snapshot_digest: str
    source_eligibility_repository_digest: str
    confidence_identities: tuple[tuple[str, str], ...]
    record_count: int
    repository_digest: str
    previous_snapshot_uuid: str | None
    previous_snapshot_digest: str | None
    generated_at: str
    confidence_policy_uuid: str
    confidence_policy_digest: str
    confidence_policy_version: str
    confidence_engine_version: str
    selector_version: str
    selection_policy_uuid: str
    selection_policy_digest: str
    selection_policy_version: str
    source_runtime_engine_version: str
    source_runtime_packaging_policy_uuid: str
    source_runtime_packaging_policy_digest: str
    source_runtime_packaging_policy_version: str
    source_registry_engine_version: str
    source_registry_admission_policy_uuid: str
    source_registry_admission_policy_digest: str
    source_registry_admission_policy_version: str
    source_promotion_engine_version: str
    source_promotion_policy_uuid: str
    source_promotion_policy_digest: str
    source_promotion_policy_version: str
    source_validator_version: str
    source_validation_policy_version: str
    source_validation_config_digest: str
    source_mining_engine_version: str
    source_mining_policy_uuid: str
    source_mining_policy_version: str
    source_mining_config_digest: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        identities = tuple(tuple(item) for item in self.confidence_identities)
        object.__setattr__(self, "confidence_identities", identities)
        previous_valid = (
            self.previous_snapshot_uuid is None
            and self.previous_snapshot_digest is None
        ) or (
            valid_uuid(self.previous_snapshot_uuid)
            and valid_digest(self.previous_snapshot_digest)
        )
        if (
            not valid_uuid(self.snapshot_uuid)
            or not valid_digest(self.snapshot_digest)
            or self.source_artifact_type not in SOURCE_ARTIFACT_TYPES
            or not valid_uuid(self.source_artifact_uuid)
            or not valid_digest(self.source_artifact_digest)
            or not valid_uuid(self.source_eligibility_snapshot_uuid)
            or not valid_digest(self.source_eligibility_snapshot_digest)
            or not valid_digest(self.source_eligibility_repository_digest)
            or identities != tuple(sorted(identities))
            or self.record_count != len(identities)
            or len({item[0] for item in identities}) != len(identities)
            or not all(
                valid_uuid(item[0]) and valid_digest(item[1]) for item in identities
            )
            or not valid_digest(self.repository_digest)
            or not previous_valid
            or not all(
                valid_uuid(getattr(self, name))
                for name in PARTITION_FIELDS
                if name.endswith("uuid")
            )
            or not all(
                valid_digest(getattr(self, name))
                for name in PARTITION_FIELDS
                if name.endswith("digest")
            )
            or not all(
                getattr(self, name)
                for name in PARTITION_FIELDS
                if name.endswith("version")
            )
            or not valid_timestamp(self.generated_at)
            or self.authority_scope != AUTHORITY_SCOPE
            or self.advisory_only is not True
            or snapshot_uuid(self.identity_payload()) != self.snapshot_uuid
            or digest(self.identity_payload()) != self.snapshot_digest
        ):
            raise ValueError("INVALID_CONFIDENCE_SNAPSHOT")

    def identity_payload(self):
        return {
            name: (
                [list(item) for item in self.confidence_identities]
                if name == "confidence_identities"
                else getattr(self, name)
            )
            for name in self.__dataclass_fields__
            if name not in {"snapshot_uuid", "snapshot_digest"}
        }

    def to_dict(self):
        return {
            "snapshot_uuid": self.snapshot_uuid,
            "snapshot_digest": self.snapshot_digest,
            **self.identity_payload(),
        }

    @classmethod
    def create(cls, **values):
        values = dict(values)
        values["confidence_identities"] = tuple(
            sorted(tuple(item) for item in values["confidence_identities"])
        )
        payload = {
            **values,
            "confidence_identities": [
                list(item) for item in values["confidence_identities"]
            ],
        }
        return cls(
            snapshot_uuid=snapshot_uuid(payload),
            snapshot_digest=digest(payload),
            **values,
        )


@dataclass(frozen=True)
class RuntimeConfidenceReport:
    report_uuid: str
    report_digest: str
    source_artifact_type: str
    source_artifact_uuid: str
    source_artifact_digest: str
    source_eligibility_snapshot_uuid: str
    source_eligibility_snapshot_digest: str
    source_eligibility_repository_digest: str
    confidence_records: tuple[ConfidenceRecord, ...]
    processed_record_count: int
    new_confidence_record_count: int
    duplicate_confidence_record_count: int
    confidence_evaluated_count: int
    insufficient_confidence_evidence_count: int
    rejected_count: int
    repository_digest: str
    snapshot_uuid: str
    snapshot_digest: str
    generated_at: str
    confidence_policy_uuid: str
    confidence_policy_digest: str
    confidence_policy_version: str
    confidence_engine_version: str
    selector_version: str
    selection_policy_uuid: str
    selection_policy_digest: str
    selection_policy_version: str
    source_runtime_engine_version: str
    source_runtime_packaging_policy_uuid: str
    source_runtime_packaging_policy_digest: str
    source_runtime_packaging_policy_version: str
    source_registry_engine_version: str
    source_registry_admission_policy_uuid: str
    source_registry_admission_policy_digest: str
    source_registry_admission_policy_version: str
    source_promotion_engine_version: str
    source_promotion_policy_uuid: str
    source_promotion_policy_digest: str
    source_promotion_policy_version: str
    source_validator_version: str
    source_validation_policy_version: str
    source_validation_config_digest: str
    source_mining_engine_version: str
    source_mining_policy_uuid: str
    source_mining_policy_version: str
    source_mining_config_digest: str
    authority_scope: str = AUTHORITY_SCOPE
    advisory_only: bool = True

    def __post_init__(self):
        records = tuple(self.confidence_records)
        object.__setattr__(self, "confidence_records", records)
        counts = (
            self.processed_record_count,
            self.new_confidence_record_count,
            self.duplicate_confidence_record_count,
            self.confidence_evaluated_count,
            self.insufficient_confidence_evidence_count,
            self.rejected_count,
        )
        partition = tuple(getattr(self, name) for name in PARTITION_FIELDS)
        if (
            not valid_uuid(self.report_uuid)
            or not valid_digest(self.report_digest)
            or self.source_artifact_type not in SOURCE_ARTIFACT_TYPES
            or not valid_uuid(self.source_artifact_uuid)
            or not valid_digest(self.source_artifact_digest)
            or not valid_uuid(self.source_eligibility_snapshot_uuid)
            or not valid_digest(self.source_eligibility_snapshot_digest)
            or not valid_digest(self.source_eligibility_repository_digest)
            or not all(type(value) is int and value >= 0 for value in counts)
            or self.processed_record_count != len(records)
            or self.new_confidence_record_count + self.duplicate_confidence_record_count
            != self.processed_record_count
            or self.confidence_evaluated_count
            + self.insufficient_confidence_evidence_count
            + self.rejected_count
            != self.processed_record_count
            or not all(type(item) is ConfidenceRecord for item in records)
            or any(
                tuple(getattr(item, name) for name in PARTITION_FIELDS) != partition
                for item in records
            )
            or self.confidence_evaluated_count
            != sum(item.confidence_state == "CONFIDENCE_EVALUATED" for item in records)
            or self.insufficient_confidence_evidence_count
            != sum(
                item.confidence_state == "INSUFFICIENT_CONFIDENCE_EVIDENCE"
                for item in records
            )
            or self.rejected_count
            != sum(item.confidence_state == "REJECTED" for item in records)
            or not valid_digest(self.repository_digest)
            or not valid_uuid(self.snapshot_uuid)
            or not valid_digest(self.snapshot_digest)
            or not valid_timestamp(self.generated_at)
            or self.authority_scope != AUTHORITY_SCOPE
            or self.advisory_only is not True
            or report_uuid(self.identity_payload()) != self.report_uuid
            or digest(self.digest_payload()) != self.report_digest
        ):
            raise ValueError("INVALID_CONFIDENCE_REPORT")

    def identity_payload(self):
        return {
            name: (
                [item.to_dict() for item in self.confidence_records]
                if name == "confidence_records"
                else getattr(self, name)
            )
            for name in self.__dataclass_fields__
            if name not in {"report_uuid", "report_digest"}
        }

    def digest_payload(self):
        return {"report_uuid": self.report_uuid, **self.identity_payload()}

    def to_dict(self):
        return {
            "report_uuid": self.report_uuid,
            "report_digest": self.report_digest,
            **self.identity_payload(),
        }

    @classmethod
    def create(cls, **values):
        values = dict(values)
        values["confidence_records"] = tuple(values["confidence_records"])
        payload = {
            **values,
            "confidence_records": [
                item.to_dict() for item in values["confidence_records"]
            ],
        }
        identity = report_uuid(payload)
        return cls(
            report_uuid=identity,
            report_digest=digest({"report_uuid": identity, **payload}),
            **values,
        )
