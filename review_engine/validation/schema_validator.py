"""Strict validation for RAIP-owned documents, independent of trading schemas."""
from __future__ import annotations
from datetime import datetime
from math import isfinite
from typing import Mapping
from uuid import UUID
from review_engine.collector.event_types import EVENT_TYPES

class SchemaValidationError(ValueError): pass

def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping): raise SchemaValidationError(f"{name}_MUST_BE_OBJECT")
    return value

def _required(doc: Mapping[str, object], names: tuple[str, ...], name: str) -> None:
    missing = [field for field in names if field not in doc]
    if missing: raise SchemaValidationError(f"{name}_MISSING:" + ",".join(missing))
def _str(value: object, name: str, nullable: bool=False) -> None:
    if value is None and nullable: return
    if not isinstance(value, str) or not value: raise SchemaValidationError(f"INVALID_{name}")
def _number(value: object, name: str, nullable: bool=False) -> None:
    if value is None and nullable: return
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not isfinite(value): raise SchemaValidationError(f"INVALID_{name}")
def _timestamp(value: object, name: str, nullable: bool=False) -> None:
    if value is None and nullable:return
    _str(value,name)
    if not value.endswith("Z"): raise SchemaValidationError(f"{name}_NOT_UTC")
    try: datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc: raise SchemaValidationError(f"INVALID_{name}") from exc

def validate_event(doc: Mapping[str, object]) -> None:
    _required(doc, ("schema_version","event_id","event_type","occurred_at_utc","observed_at_utc","source_module","source_version","symbol","account_id_hash","trade_id","position_id","series_id","candidate_id","sequence_id","correlation_id","payload","integrity"), "EVENT")
    for key in ("schema_version","source_module","source_version","symbol"): _str(doc[key],key)
    try: UUID(str(doc["event_id"]))
    except ValueError as exc: raise SchemaValidationError("INVALID_EVENT_ID") from exc
    if doc["event_type"] not in EVENT_TYPES: raise SchemaValidationError("INVALID_EVENT_TYPE")
    _timestamp(doc["occurred_at_utc"],"occurred_at_utc"); _timestamp(doc["observed_at_utc"],"observed_at_utc")
    for key in ("account_id_hash","trade_id","position_id","series_id","candidate_id","sequence_id","correlation_id"): _str(doc[key],key,True)
    _mapping(doc["payload"], "payload")
    integrity = _mapping(doc["integrity"], "integrity"); _str(integrity.get("payload_sha256"),"payload_sha256")

def validate_snapshot(doc: Mapping[str, object]) -> None:
    _required(doc,("schema_version","snapshot_id","created_at_utc","trade_identity","timeline","decision_context","market_context","execution_context","outcome","data_quality","provenance"),"SNAPSHOT")
    _str(doc["schema_version"],"schema_version"); _timestamp(doc["created_at_utc"],"created_at_utc")
    try: UUID(str(doc["snapshot_id"]))
    except ValueError as exc: raise SchemaValidationError("INVALID_SNAPSHOT_ID") from exc
    identity=_mapping(doc["trade_identity"],"trade_identity"); _required(identity,("trade_id","position_id","series_id","symbol","side","volume"),"IDENTITY"); _str(identity["trade_id"],"trade_id"); _str(identity["symbol"],"symbol");
    if identity["side"] not in {"BUY","SELL"}: raise SchemaValidationError("INVALID_SIDE")
    _number(identity["volume"],"volume")
    timeline=_mapping(doc["timeline"],"timeline"); _required(timeline,("decision_at_utc","entry_requested_at_utc","filled_at_utc","closed_at_utc","duration_seconds"),"TIMELINE")
    for key in ("decision_at_utc","entry_requested_at_utc","filled_at_utc","closed_at_utc"): _timestamp(timeline[key],key,True)
    _number(timeline["duration_seconds"],"duration_seconds",True)
    execution=_mapping(doc["execution_context"],"execution_context"); _required(execution,("requested_price","entry_price","exit_price","spread_points_at_entry","slippage_points","commission","swap"),"EXECUTION")
    for key in execution: _number(execution[key],key, key in {"requested_price","spread_points_at_entry","slippage_points"})
    outcome=_mapping(doc["outcome"],"outcome"); _required(outcome,("gross_profit","net_profit","profit_points","r_multiple","mae_points","mfe_points","exit_reason"),"OUTCOME")
    for key in ("gross_profit","net_profit"): _number(outcome[key],key)
    quality=_mapping(doc["data_quality"],"data_quality"); _required(quality,("completeness_ratio","missing_fields","warnings","source_event_count"),"QUALITY"); _number(quality["completeness_ratio"],"completeness_ratio")
    if not isinstance(quality["missing_fields"],list) or not isinstance(quality["warnings"],list): raise SchemaValidationError("INVALID_QUALITY_LIST")
    provenance=_mapping(doc["provenance"],"provenance"); _required(provenance,("source_event_ids","builder_version","snapshot_sha256"),"PROVENANCE")
    if not isinstance(provenance["source_event_ids"],list): raise SchemaValidationError("INVALID_SOURCE_EVENT_IDS")
    _str(provenance["builder_version"],"builder_version"); _str(provenance["snapshot_sha256"],"snapshot_sha256")

def validate_daily_review(doc: Mapping[str, object]) -> None:
    _required(doc,("schema_version","date_utc","generated_at_utc","scope","performance","direction","data_quality","provenance"),"REVIEW")
    _str(doc["schema_version"],"schema_version"); _str(doc["date_utc"],"date_utc"); _timestamp(doc["generated_at_utc"],"generated_at_utc")
    scope=_mapping(doc["scope"],"scope"); _required(scope,("symbols","trade_count","complete_snapshot_count","incomplete_snapshot_count"),"SCOPE")
    performance=_mapping(doc["performance"],"performance"); _required(performance,("wins","losses","breakeven","win_rate","gross_profit","net_profit","profit_factor","average_win","average_loss","average_duration_seconds"),"PERFORMANCE")
    direction=_mapping(doc["direction"],"direction"); _required(direction,("buy_trades","sell_trades","buy_net_profit","sell_net_profit"),"DIRECTION")
    quality=_mapping(doc["data_quality"],"data_quality"); _required(quality,("average_completeness_ratio","missing_field_counts","warnings"),"QUALITY")
    provenance=_mapping(doc["provenance"],"provenance"); _required(provenance,("snapshot_ids","builder_version","report_sha256"),"PROVENANCE")
