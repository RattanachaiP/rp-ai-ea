"""Canonical dimensional contracts and immutable output of Risk Construction."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Mapping

SCHEMA_VERSION="V28.EXECUTION_PLAN.1.1"; POLICY_ID="V28_RISK_CONSTRUCTION_POLICY"; POLICY_VERSION="1.1.0"

def parse_utc(value: str) -> datetime:
    try: parsed=datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError): raise ValueError("TIMESTAMP_INVALID")
    if parsed.tzinfo is None or parsed.utcoffset() is None: raise ValueError("TIMESTAMP_INVALID")
    return parsed.astimezone(timezone.utc)

def _plain(value: Any) -> Any:
    if hasattr(value,"__dataclass_fields__"): return {k:_plain(getattr(value,k)) for k in value.__dataclass_fields__}
    if isinstance(value,Mapping): return {str(k):_plain(v) for k,v in sorted(value.items())}
    if isinstance(value,(tuple,list)): return [_plain(v) for v in value]
    return value

def identity(domain: str, payload: Any) -> str:
    raw=json.dumps(_plain(payload),sort_keys=True,separators=(",",":"),allow_nan=False)
    return sha256((domain+"|"+raw).encode()).hexdigest()

def _finite(value, *, positive=False, nonnegative=False):
    valid=type(value) in (int,float) and isfinite(value)
    if not valid or (positive and value<=0) or (nonnegative and value<0): raise ValueError("NUMERIC_UNIT_INVALID")

@dataclass(frozen=True)
class ExecutableQuote:
    symbol: str; bid: float; ask: float; timestamp: str; sequence_id: int; source: str
    maximum_age_seconds: float; maximum_slippage_price: float
    def __post_init__(self):
        if not self.symbol or not self.source or type(self.sequence_id) is not int or self.sequence_id<0: raise ValueError("QUOTE_IDENTITY_INVALID")
        for v in (self.bid,self.ask,self.maximum_slippage_price): _finite(v,nonnegative=True)
        _finite(self.maximum_age_seconds,positive=True)
        if self.bid<=0 or self.ask<self.bid: raise ValueError("QUOTE_PRICE_INVALID")
        parse_utc(self.timestamp)

@dataclass(frozen=True)
class ExecutionConstraints:
    quote: ExecutableQuote | None
    protective_stop: float | None
    target: float | None
    volatility_distance_price: float | None
    optional_requested_volume_cap: float | None
    minimum_net_reward_risk_ratio: float
    commission_account_currency_per_volume: float
    slippage_account_currency_per_volume: float
    other_cost_account_currency_per_volume: float
    execution_model_id: str; cost_model_id: str; evaluation_time: str
    maximum_runtime_age_seconds: float; maximum_boundary_age_seconds: float
    decision_market_sequence_id: int; runtime_health_valid: bool
    def __post_init__(self):
        if (not self.execution_model_id or not self.cost_model_id or type(self.decision_market_sequence_id) is not int
            or self.decision_market_sequence_id<0 or type(self.runtime_health_valid) is not bool): raise ValueError("EXECUTION_CONSTRAINT_IDENTITY_INVALID")
        if self.quote is not None and not isinstance(self.quote,ExecutableQuote): raise ValueError("EXECUTION_QUOTE_INVALID")
        parse_utc(self.evaluation_time)
        for v in (self.minimum_net_reward_risk_ratio,self.maximum_runtime_age_seconds,self.maximum_boundary_age_seconds): _finite(v,positive=True)
        for v in (self.commission_account_currency_per_volume,self.slippage_account_currency_per_volume,self.other_cost_account_currency_per_volume): _finite(v,nonnegative=True)
        for v in (self.protective_stop,self.target,self.volatility_distance_price,self.optional_requested_volume_cap):
            if v is not None: _finite(v,positive=True)

@dataclass(frozen=True)
class ExecutionPlan:
    decision_replay_identity: str; runtime_sequence_id: int; symbol: str; direction: str
    executable_entry_price: float | None; approved_volume: float
    volume_step: float | None; tick_size: float | None
    protective_stop: float | None; target: float | None
    stop_distance_price: float | None; stop_distance_points: float | None
    monetary_risk_per_volume: float | None; margin_required_per_volume: float | None
    execution_model_id: str; cost_model_id: str; evaluation_time: str
    approval_status: str; execution_ready: bool; validation_reasons: tuple[str,...]
    policy_references: tuple[str,...]; replay_identity: str
    policy_version: str=POLICY_VERSION; schema_version: str=SCHEMA_VERSION
    def canonical_payload(self): return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if not self.decision_replay_identity or not self.symbol or not self.execution_model_id or not self.cost_model_id: raise ValueError("EXECUTION_PLAN_LINEAGE_INVALID")
        if self.direction not in {"BUY","SELL","NONE"} or self.approval_status not in {"APPROVED","REJECTED","DEFERRED"}: raise ValueError("EXECUTION_PLAN_ONTOLOGY_INVALID")
        _finite(self.approved_volume,nonnegative=True); parse_utc(self.evaluation_time)
        ready=self.approval_status=="APPROVED"
        if self.execution_ready!=ready: raise ValueError("EXECUTION_PLAN_APPROVAL_INVALID")
        if ready:
            values=(self.executable_entry_price,self.protective_stop,self.target,self.stop_distance_price,self.stop_distance_points,self.monetary_risk_per_volume,self.margin_required_per_volume)
            if self.direction=="NONE" or any(v is None for v in values) or self.approved_volume<=0: raise ValueError("EXECUTION_PLAN_READY_INCOMPLETE")
            _finite(self.volume_step,positive=True); _finite(self.tick_size,positive=True)
            if self.validation_reasons!=("ALL_RISK_CONSTRUCTION_CHECKS_VALID",) or len(self.policy_references)<2: raise ValueError("EXECUTION_PLAN_READY_POLICY_INVALID")
            if self.direction=="BUY" and not self.protective_stop<self.executable_entry_price<self.target: raise ValueError("EXECUTION_PLAN_PRICE_SIDES_INVALID")
            if self.direction=="SELL" and not self.target<self.executable_entry_price<self.protective_stop: raise ValueError("EXECUTION_PLAN_PRICE_SIDES_INVALID")
            from decimal import Decimal
            if Decimal(str(self.approved_volume))%Decimal(str(self.volume_step))!=0: raise ValueError("EXECUTION_PLAN_VOLUME_NORMALIZATION_INVALID")
            if any(Decimal(str(v))%Decimal(str(self.tick_size))!=0 for v in (self.executable_entry_price,self.protective_stop,self.target)): raise ValueError("EXECUTION_PLAN_PRICE_NORMALIZATION_INVALID")
        elif self.approved_volume!=0 or self.executable_entry_price is not None or self.volume_step is not None or self.tick_size is not None: raise ValueError("EXECUTION_PLAN_NONEXECUTABLE_SHAPE_INVALID")
        if not self.validation_reasons or self.replay_identity!=identity("V28_EXECUTION_PLAN_REPLAY",self.canonical_payload()): raise ValueError("EXECUTION_PLAN_REPLAY_INVALID")
