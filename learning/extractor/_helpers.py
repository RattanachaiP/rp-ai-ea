from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from .registry import FeatureRegistry

def value(evidence: Mapping[str, Any], name: str, default: Any = None) -> Any:
    if name in evidence: return evidence[name]
    for section in ("market", "market_context", "execution", "execution_context", "outcome", "structure", "indicators"):
        child = evidence.get(section)
        if isinstance(child, Mapping) and name in child: return child[name]
    return default

def enum(name: str, candidate: object) -> str:
    definition = FeatureRegistry.get(name)
    normalized = str(candidate).upper().replace(" ", "_") if candidate is not None else "UNKNOWN"
    return normalized if normalized in definition.allowed_values else "UNKNOWN"
def bucket(number: object, name: str, low: float, high: float, labels: tuple[str, str, str]) -> str:
    try: n = abs(float(number))
    except (TypeError, ValueError): return enum(name, None)
    return enum(name, labels[0] if n < low else labels[1] if n < high else labels[2])
def boolean(raw: object) -> bool:
    return raw is True or str(raw).upper() in ("TRUE", "1", "YES")
