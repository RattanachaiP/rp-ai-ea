"""Immutable, replay-bound authority contracts for PR264."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from .execution_plan import _finite, identity, parse_utc

PR264_POLICY = "V28_EXECUTION_INTEGRATION_POLICY@2.0.0"


def _required_text(value: str, reason: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError(reason)


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class RuntimeHealthSnapshot:
    healthy: bool; runtime_sequence_id: int; source_authority: str
    observed_at: str; evaluation_time: str; expires_at: str
    maximum_age_seconds: float; policy_reference: str; replay_identity: str

    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "replay_identity"}
    def __post_init__(self):
        if type(self.healthy) is not bool or type(self.runtime_sequence_id) is not int or self.runtime_sequence_id < 0: raise ValueError("RUNTIME_HEALTH_INVALID")
        for value in (self.source_authority, self.policy_reference): _required_text(value, "RUNTIME_HEALTH_AUTHORITY_INVALID")
        for value in (self.observed_at, self.evaluation_time, self.expires_at): parse_utc(value)
        _finite(self.maximum_age_seconds, positive=True)
        if self.replay_identity != identity("V28_RUNTIME_HEALTH_SNAPSHOT_REPLAY", self.canonical_payload()): raise ValueError("RUNTIME_HEALTH_REPLAY_INVALID")


@dataclass(frozen=True)
class ExecutionEnvironmentContract:
    environment: str; account_identifier: str; account_type: str; broker_server: str
    terminal_instance_identity: str; executor_instance_identity: str
    verified_source_authority: str; verification_timestamp: str; expires_at: str
    policy_reference: str; replay_identity: str

    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "replay_identity"}
    def __post_init__(self):
        if self.environment != "DEMO" or self.account_type != "DEMO": raise ValueError("DEMO_ENVIRONMENT_REQUIRED")
        for field in ("account_identifier", "broker_server", "terminal_instance_identity", "executor_instance_identity", "verified_source_authority", "policy_reference"):
            _required_text(getattr(self, field), "ENVIRONMENT_AUTHORITY_INVALID")
        parse_utc(self.verification_timestamp); parse_utc(self.expires_at)
        if self.replay_identity != identity("V28_EXECUTION_ENVIRONMENT_REPLAY", self.canonical_payload()): raise ValueError("ENVIRONMENT_REPLAY_INVALID")


@dataclass(frozen=True)
class BrokerSnapshot:
    account_environment: str; account_identifier: str; broker_server: str; terminal_instance_identity: str
    symbol: str; runtime_sequence_id: int; trading_enabled: bool; session_state: str
    symbol_trade_mode: str; connection_state: str; source_authority: str
    observed_at: str; evaluation_time: str; expires_at: str; maximum_age_seconds: float
    policy_reference: str; replay_identity: str

    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "replay_identity"}
    def __post_init__(self):
        if self.account_environment != "DEMO" or type(self.runtime_sequence_id) is not int or self.runtime_sequence_id < 0 or type(self.trading_enabled) is not bool: raise ValueError("BROKER_SNAPSHOT_INVALID")
        for field in ("account_identifier", "broker_server", "terminal_instance_identity", "symbol", "session_state", "symbol_trade_mode", "connection_state", "source_authority", "policy_reference"):
            _required_text(getattr(self, field), "BROKER_SNAPSHOT_AUTHORITY_INVALID")
        for value in (self.observed_at, self.evaluation_time, self.expires_at): parse_utc(value)
        _finite(self.maximum_age_seconds, positive=True)
        if self.replay_identity != identity("V28_BROKER_SNAPSHOT_REPLAY", self.canonical_payload()): raise ValueError("BROKER_SNAPSHOT_REPLAY_INVALID")


@dataclass(frozen=True)
class HumanApprovalRecord:
    approval_id: str; approver_identity: str; approval_authority: str
    execution_plan_replay_identity: str; executor_contract_replay_identity: str
    approved_environment_identity: str; approval_timestamp: str; expires_at: str
    policy_reference: str; nonce: str; replay_identity: str

    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "replay_identity"}
    def __post_init__(self):
        for field in self.__dataclass_fields__:
            if field not in {"approval_timestamp", "expires_at", "replay_identity"}: _required_text(getattr(self, field), "HUMAN_APPROVAL_INVALID")
        parse_utc(self.approval_timestamp); parse_utc(self.expires_at)
        if self.replay_identity != identity("V28_HUMAN_APPROVAL_REPLAY", self.canonical_payload()): raise ValueError("HUMAN_APPROVAL_REPLAY_INVALID")


@dataclass(frozen=True)
class PublishedExecutionPlan:
    canonical_plan_json: str; publisher_authority: str; publisher_instance_identity: str
    publication_timestamp: str; destination_identity: str; generation: int
    policy_reference: str; schema_version: str; execution_plan_replay_identity: str
    decision_replay_identity: str; runtime_sequence_id: int; canonical_payload_hash: str
    publication_replay_identity: str

    def canonical_payload(self): return {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "publication_replay_identity"}
    def plan_payload(self) -> dict[str, Any]: return json.loads(self.canonical_plan_json)
    def __post_init__(self):
        for field in ("publisher_authority", "publisher_instance_identity", "destination_identity", "policy_reference", "execution_plan_replay_identity", "decision_replay_identity"):
            _required_text(getattr(self, field), "PUBLISHER_AUTHORITY_INVALID")
        if self.schema_version != "V28.PUBLISHED_EXECUTION_PLAN.2.0" or type(self.generation) is not int or self.generation < 0 or type(self.runtime_sequence_id) is not int: raise ValueError("PUBLISHER_SCHEMA_INVALID")
        parse_utc(self.publication_timestamp)
        try:
            decoded = json.loads(self.canonical_plan_json)
            if canonical_json(decoded) != self.canonical_plan_json: raise ValueError
        except (TypeError, ValueError, json.JSONDecodeError) as error: raise ValueError("PUBLISHED_PAYLOAD_CANONICAL_INVALID") from error
        if sha256(self.canonical_plan_json.encode()).hexdigest() != self.canonical_payload_hash: raise ValueError("PUBLISHED_PAYLOAD_HASH_INVALID")
        if self.publication_replay_identity != identity("V28_EXECUTION_PUBLICATION_REPLAY", self.canonical_payload()): raise ValueError("PUBLISHED_PAYLOAD_INTEGRITY_INVALID")


def replay_bound(contract_type, domain: str, **values):
    """Construct a contract with its identity; useful to governed boundary producers."""
    return contract_type(**values, replay_identity=identity(domain, values))
