"""Governed broker/symbol specifications and pure feasibility validation."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR
from .execution_plan import _finite, identity, parse_utc

@dataclass(frozen=True)
class SymbolSpecification:
    symbol: str; digits: int; point_size: float; tick_size: float; tick_value_per_volume: float
    contract_size: float; minimum_volume: float; maximum_volume: float; volume_step: float
    stop_level_points: int; freeze_level_points: int; margin_required_per_volume: float
    profit_currency: str; margin_currency: str; account_currency: str
    account_currency_conversion_identity: str; account_currency_conversion_rate: float
    as_of: str; replay_identity: str
    def canonical_payload(self): return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if not all((self.symbol,self.profit_currency,self.margin_currency,self.account_currency,self.account_currency_conversion_identity)): raise ValueError("SYMBOL_SPEC_IDENTITY_INVALID")
        if type(self.digits) is not int or self.digits<0 or type(self.stop_level_points) is not int or type(self.freeze_level_points) is not int or min(self.stop_level_points,self.freeze_level_points)<0: raise ValueError("SYMBOL_SPEC_POINTS_INVALID")
        for v in (self.point_size,self.tick_size,self.tick_value_per_volume,self.contract_size,self.minimum_volume,self.maximum_volume,self.volume_step,self.margin_required_per_volume,self.account_currency_conversion_rate): _finite(v,positive=True)
        if (self.minimum_volume>self.maximum_volume or Decimal(str(self.tick_size))%Decimal(str(self.point_size))!=0
            or Decimal(str(self.minimum_volume))%Decimal(str(self.volume_step))!=0
            or Decimal(str(self.maximum_volume))%Decimal(str(self.volume_step))!=0): raise ValueError("SYMBOL_SPEC_RANGE_INVALID")
        parse_utc(self.as_of)
        if self.replay_identity!=identity("V28_SYMBOL_SPEC_REPLAY",self.canonical_payload()): raise ValueError("SYMBOL_SPEC_REPLAY_INVALID")

def create_symbol_specification(**values):
    return SymbolSpecification(**values,replay_identity=identity("V28_SYMBOL_SPEC_REPLAY",values))

@dataclass(frozen=True)
class BrokerConstraints:
    symbol: str; trading_session_open: bool; symbol_available: bool; as_of: str
    evaluation_time: str; source: str; replay_identity: str
    def canonical_payload(self): return {k:getattr(self,k) for k in self.__dataclass_fields__ if k!="replay_identity"}
    def __post_init__(self):
        if not self.symbol or not self.source: raise ValueError("BROKER_IDENTITY_INVALID")
        if type(self.trading_session_open) is not bool or type(self.symbol_available) is not bool: raise ValueError("BROKER_STATE_INVALID")
        parse_utc(self.as_of); parse_utc(self.evaluation_time)
        if self.replay_identity!=identity("V28_BROKER_CONSTRAINT_REPLAY",self.canonical_payload()): raise ValueError("BROKER_REPLAY_INVALID")

def create_broker_constraints(**values): return BrokerConstraints(**values,replay_identity=identity("V28_BROKER_CONSTRAINT_REPLAY",values))

def floor_volume(value,spec):
    steps=(Decimal(str(value))/Decimal(str(spec.volume_step))).to_integral_value(rounding=ROUND_FLOOR)
    return float(steps*Decimal(str(spec.volume_step)))

def tick_aligned(value,spec): return Decimal(str(value))%Decimal(str(spec.tick_size))==0

def validate_broker_constraints(broker,spec,*,volume,stop_distance_points,target_distance_points,free_margin):
    reasons=[]
    if broker.symbol!=spec.symbol: reasons.append("BROKER_SYMBOL_MISMATCH")
    if not broker.symbol_available: reasons.append("SYMBOL_UNAVAILABLE")
    if not broker.trading_session_open: reasons.append("TRADING_SESSION_CLOSED")
    if not spec.minimum_volume<=volume<=spec.maximum_volume: reasons.append("VOLUME_OUT_OF_RANGE")
    if floor_volume(volume,spec)!=volume: reasons.append("VOLUME_STEP_INVALID")
    if min(stop_distance_points,target_distance_points)<spec.stop_level_points: reasons.append("STOP_LEVEL_VIOLATION")
    if min(stop_distance_points,target_distance_points)<=spec.freeze_level_points: reasons.append("FREEZE_LEVEL_VIOLATION")
    if volume*spec.margin_required_per_volume>free_margin: reasons.append("BROKER_MARGIN_INSUFFICIENT")
    return ("INVALID" if reasons else "VALID",tuple(reasons) or ("BROKER_CONSTRAINTS_VALID",))
