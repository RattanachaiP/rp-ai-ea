"""Canonical identities for PR271 training artifacts."""
import hashlib
import json
from dataclasses import asdict, is_dataclass
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping


def canonical(value: Any) -> Any:
    if is_dataclass(value): return canonical(asdict(value))
    if isinstance(value, Mapping): return {str(k): canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, (tuple, list)): return [canonical(v) for v in value]
    if value is None or isinstance(value, (str, bool, int)): return value
    if isinstance(value, float) and isfinite(value): return value
    raise ValueError("TRAINING_CANONICAL_VALUE_INVALID")


def identity_for(kind: str, payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(canonical(payload), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(b"RP-AI-EA/PR271/" + kind.encode() + b"/V1\0" + encoded).hexdigest()
