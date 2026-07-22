"""Dependency-free structural validation for RAIP's versioned JSON contracts."""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

class SchemaValidationError(ValueError): pass
ROOT = Path(__file__).parents[1] / "schemas"

def _load(name): return json.loads((ROOT / name).read_text(encoding="utf-8"))
def _timestamp(value):
    if not isinstance(value, str): return False
    try: datetime.fromisoformat(value.replace("Z", "+00:00")); return value.endswith("Z") or "+00:00" in value
    except ValueError: return False
def _check(value: Any, spec: Mapping[str, Any], path="$"):
    typ = spec.get("type")
    types = typ if isinstance(typ, list) else [typ]
    ok = {"object":lambda: isinstance(value, dict), "array":lambda:isinstance(value,list), "string":lambda:isinstance(value,str), "number":lambda:isinstance(value,(int,float)) and not isinstance(value,bool), "integer":lambda:isinstance(value,int) and not isinstance(value,bool), "null":lambda:value is None, "boolean":lambda:isinstance(value,bool)}
    if typ and not any(ok[x]() for x in types): raise SchemaValidationError(f"{path}: expected {typ}")
    if "enum" in spec and value not in spec["enum"]: raise SchemaValidationError(f"{path}: unsupported value")
    if value is not None and spec.get("format") == "date-time" and not _timestamp(value): raise SchemaValidationError(f"{path}: invalid UTC timestamp")
    if value is not None and spec.get("format") == "date":
        try: datetime.strptime(value, "%Y-%m-%d")
        except (ValueError, TypeError): raise SchemaValidationError(f"{path}: invalid date")
    if isinstance(value, dict):
        for key in spec.get("required", []):
            if key not in value: raise SchemaValidationError(f"{path}: missing {key}")
        props = spec.get("properties", {})
        if spec.get("additionalProperties") is False:
            unknown = set(value) - set(props)
            if unknown: raise SchemaValidationError(f"{path}: unknown {sorted(unknown)[0]}")
        for key, child in props.items():
            if key in value: _check(value[key], child, f"{path}.{key}")
    if isinstance(value, list):
        if len(value) < spec.get("minItems", 0): raise SchemaValidationError(f"{path}: too few items")
        for i, child in enumerate(value): _check(child, spec.get("items", {}), f"{path}[{i}]")
def validate(instance, schema_name): _check(instance, _load(schema_name)); return True
def validate_event(event): return validate(event, "event.schema.json")
def validate_snapshot(snapshot): return validate(snapshot, "trade_snapshot.schema.json")
def validate_daily_review(review): return validate(review, "daily_review.schema.json")
