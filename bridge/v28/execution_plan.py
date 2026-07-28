"""Canonical immutable output of V28 Risk Construction."""
from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping

SCHEMA_VERSION = "V28.EXECUTION_PLAN.1.0"
POLICY_ID = "V28_RISK_CONSTRUCTION_POLICY"
POLICY_VERSION = "1.0.0"

def _plain(value):
    if hasattr(value, "__dataclass_fields__"):
        return {k: _plain(getattr(value, k)) for k in value.__dataclass_fields__}
    if isinstance(value, Mapping): return {k: _plain(v) for k, v in sorted(value.items())}
    if isinstance(value, (tuple, list)): return [_plain(v) for v in value]
    return value

def plan_identity(payload):
    raw=json.dumps(_plain(payload), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256(("V28_EXECUTION_PLAN_REPLAY|"+raw).encode()).hexdigest()

@dataclass(frozen=True)
class ExecutionConstraints:
    entry_price: float | None
    protective_stop: float | None
    target: float | None
    requested_volume: float | None
    volatility_distance: float | None
    minimum_reward_risk: float
    maximum_runtime_age_seconds: float
    execution_model_id: str

@dataclass(frozen=True)
class ExecutionPlan:
    decision_replay_identity: str
    runtime_sequence_id: int
    symbol: str
    direction: str
    volume: float
    protective_stop: float | None
    target: float | None
    execution_constraints: ExecutionConstraints
    approval_status: str
    execution_ready: bool
    validation_reasons: tuple[str, ...]
    policy_references: tuple[str, ...]
    replay_identity: str
    policy_version: str = POLICY_VERSION
    schema_version: str = SCHEMA_VERSION

    def canonical_payload(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "replay_identity"}

    def __post_init__(self):
        if self.direction not in {"BUY", "SELL", "NONE"} or self.approval_status not in {"APPROVED", "REJECTED", "DEFERRED"}:
            raise ValueError("EXECUTION_PLAN_ONTOLOGY_INVALID")
        if self.execution_ready != (self.approval_status == "APPROVED"):
            raise ValueError("EXECUTION_PLAN_APPROVAL_INVALID")
        if self.execution_ready and (self.direction == "NONE" or self.volume <= 0 or self.protective_stop is None or self.target is None):
            raise ValueError("EXECUTION_PLAN_READY_INCOMPLETE")
        if not self.validation_reasons or self.replay_identity != plan_identity(self.canonical_payload()):
            raise ValueError("EXECUTION_PLAN_REPLAY_INVALID")
        object.__setattr__(self, "validation_reasons", tuple(self.validation_reasons))
        object.__setattr__(self, "policy_references", tuple(self.policy_references))
