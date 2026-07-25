"""Immutable, advisory-only PR178 promotion artifacts."""
from dataclasses import dataclass
from learning.pattern_memory.models import valid_digest, valid_timestamp, valid_uuid
from .identity import digest, promotion_report_uuid, promotion_snapshot_uuid, promotion_uuid

PROMOTION_STATES = ("REJECTED", "NOT_YET_ELIGIBLE", "PROMOTION_ELIGIBLE")


@dataclass(frozen=True)
class PromotionRecord:
    promotion_uuid: str
    promotion_digest: str
    validation_uuid: str
    validation_digest: str
    memory_uuid: str
    pattern_uuid: str
    policy_uuid: str
    knowledge_uuid: str
    promotion_state: str
    promotion_reasons: tuple[str, ...]
    promotion_policy_version: str
    created_at: str
    advisory_only: bool = True

    def __post_init__(self):
        object.__setattr__(self, "promotion_reasons", tuple(self.promotion_reasons))
        if (not all(valid_uuid(x) for x in (self.promotion_uuid, self.validation_uuid,
                self.memory_uuid, self.pattern_uuid, self.policy_uuid, self.knowledge_uuid))
                or not all(valid_digest(x) for x in (self.promotion_digest, self.validation_digest))
                or self.promotion_state not in PROMOTION_STATES or not self.promotion_reasons
                or not all(isinstance(x, str) and x for x in self.promotion_reasons)
                or not self.promotion_policy_version or not valid_timestamp(self.created_at)
                or self.advisory_only is not True
                or promotion_uuid(self.identity_payload()) != self.promotion_uuid
                or digest(self.digest_payload()) != self.promotion_digest):
            raise ValueError("INVALID_PROMOTION_RECORD")

    def identity_payload(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__
                if name not in {"promotion_uuid", "promotion_digest"}}

    def digest_payload(self): return {"promotion_uuid": self.promotion_uuid, **self.identity_payload()}
    def to_dict(self): return {"promotion_uuid": self.promotion_uuid,
        "promotion_digest": self.promotion_digest, **self.identity_payload()}

    @classmethod
    def create(cls, **values):
        identifier = promotion_uuid(values)
        return cls(promotion_uuid=identifier,
                   promotion_digest=digest({"promotion_uuid": identifier, **values}), **values)


@dataclass(frozen=True)
class PatternPromotionSnapshot:
    snapshot_uuid: str
    snapshot_digest: str
    record_identities: tuple[tuple[str, str], ...]
    previous_snapshot_uuid: str | None
    previous_snapshot_digest: str | None
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        pairs = tuple(tuple(x) for x in self.record_identities)
        object.__setattr__(self, "record_identities", pairs)
        payload = self.identity_payload()
        if (not valid_uuid(self.snapshot_uuid) or not valid_digest(self.snapshot_digest)
                or pairs != tuple(sorted(pairs)) or len({x[0] for x in pairs}) != len(pairs)
                or not all(len(x) == 2 and valid_uuid(x[0]) and valid_digest(x[1]) for x in pairs)
                or (self.previous_snapshot_uuid is None) != (self.previous_snapshot_digest is None)
                or (self.previous_snapshot_uuid and not valid_uuid(self.previous_snapshot_uuid))
                or (self.previous_snapshot_digest and not valid_digest(self.previous_snapshot_digest))
                or not valid_timestamp(self.generated_at) or self.advisory_only is not True
                or promotion_snapshot_uuid(payload) != self.snapshot_uuid or digest(payload) != self.snapshot_digest):
            raise ValueError("INVALID_PROMOTION_SNAPSHOT")

    def identity_payload(self):
        return {"record_identities": [list(x) for x in self.record_identities],
                "previous_snapshot_uuid": self.previous_snapshot_uuid,
                "previous_snapshot_digest": self.previous_snapshot_digest,
                "generated_at": self.generated_at, "advisory_only": self.advisory_only}
    def to_dict(self): return {"snapshot_uuid": self.snapshot_uuid,
        "snapshot_digest": self.snapshot_digest, **self.identity_payload()}

    @classmethod
    def create(cls, pairs, previous, generated_at):
        values = {"record_identities": tuple(sorted(pairs)),
                  "previous_snapshot_uuid": previous.snapshot_uuid if previous else None,
                  "previous_snapshot_digest": previous.snapshot_digest if previous else None,
                  "generated_at": generated_at, "advisory_only": True}
        payload = {**values, "record_identities": [list(x) for x in values["record_identities"]]}
        return cls(promotion_snapshot_uuid(payload), digest(payload), **values)


@dataclass(frozen=True)
class PatternPromotionReport:
    report_uuid: str
    promotion_records: tuple[PromotionRecord, ...]
    eligible_count: int
    rejected_count: int
    pending_count: int
    repository_digest: str
    generated_at: str
    advisory_only: bool = True

    def __post_init__(self):
        records = tuple(self.promotion_records); object.__setattr__(self, "promotion_records", records)
        payload = self.identity_payload()
        counts = (sum(x.promotion_state == "PROMOTION_ELIGIBLE" for x in records),
                  sum(x.promotion_state == "REJECTED" for x in records),
                  sum(x.promotion_state == "NOT_YET_ELIGIBLE" for x in records))
        if (not valid_uuid(self.report_uuid) or not all(isinstance(x, PromotionRecord) for x in records)
                or counts != (self.eligible_count, self.rejected_count, self.pending_count)
                or not valid_digest(self.repository_digest) or not valid_timestamp(self.generated_at)
                or self.advisory_only is not True or promotion_report_uuid(payload) != self.report_uuid):
            raise ValueError("INVALID_PROMOTION_REPORT")

    def identity_payload(self):
        return {"promotion_records": [x.to_dict() for x in self.promotion_records],
                "eligible_count": self.eligible_count, "rejected_count": self.rejected_count,
                "pending_count": self.pending_count, "repository_digest": self.repository_digest,
                "generated_at": self.generated_at, "advisory_only": self.advisory_only}
    def to_dict(self): return {"report_uuid": self.report_uuid, **self.identity_payload()}

    @classmethod
    def create(cls, **values):
        payload = {**values, "promotion_records": [x.to_dict() for x in values["promotion_records"]]}
        return cls(report_uuid=promotion_report_uuid(payload), **values)
