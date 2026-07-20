"""Deterministic V29.1 entry-timing quality gate.

The engine consumes an already-decided direction.  It deliberately does not
produce, invert, or otherwise alter that direction; it only returns EXECUTE or
WAIT_FOR_BETTER_ENTRY for the nominated side.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

LOGGER = logging.getLogger(__name__)
ACCEPTANCE_SCORE = 70
_MINIMUM_COMPONENT_SCORE = 60


def _number(market: Dict[str, Any], name: str, default: float = 0.0) -> float:
    try:
        return float(market.get(name, default))
    except (TypeError, ValueError):
        return default


def _directional(value: str, direction: str) -> bool:
    expected = "UP" if direction == "BUY" else "DOWN"
    return expected in value


def _components(direction: str, market: Dict[str, Any]) -> tuple[Dict[str, int], Dict[str, str]]:
    """Calculate bounded timing observations using only existing telemetry."""
    structure = str(market.get("structure_trend", market.get("market_structure", ""))).upper()
    bb_state = str(market.get("bb_state", "")).upper()
    market_mode = str(market.get("market_mode", "")).upper()
    rsi = _number(market, "rsi", 50.0)
    macd = _number(market, "macd_histogram")

    structure_score = 100 if _directional(structure, direction) else (80 if bb_state == ("WALK_UP" if direction == "BUY" else "WALK_DOWN") else 20)
    momentum_aligned = (direction == "BUY" and macd > 0 and rsi >= 50) or (direction == "SELL" and macd < 0 and rsi <= 50)
    momentum_score = 100 if momentum_aligned else 20

    extreme = bb_state in {"EXTREME_UP", "EXTREME_DOWN"}
    exhausted = (direction == "BUY" and rsi >= 75) or (direction == "SELL" and rsi <= 25)
    location_score = 0 if extreme or exhausted else (85 if bb_state in {"WALK_UP", "WALK_DOWN"} else 70)
    if exhausted:
        exhaustion_score = 0
    elif (direction == "BUY" and rsi >= 70) or (direction == "SELL" and rsi <= 30):
        exhaustion_score = 50
    else:
        exhaustion_score = 100
    market_quality_score = 100 if market_mode in {"TREND", "TRENDING"} else (55 if market_mode == "RANGE" else 70)

    scores = {
        "structure": structure_score,
        "momentum": momentum_score,
        "location": location_score,
        "exhaustion": exhaustion_score,
        "market_quality": market_quality_score,
    }
    labels = {
        "structure": "STRUCTURE_ALIGNED" if structure_score >= 60 else "STRUCTURE_NOT_ALIGNED",
        "momentum": "MOMENTUM_ALIGNED" if momentum_score >= 60 else "MOMENTUM_NOT_ALIGNED",
        "location": "LOCATION_FAVOURABLE" if location_score >= 60 else "LOCATION_EXTENDED",
        "exhaustion": "MOVE_NOT_EXHAUSTED" if exhaustion_score >= 60 else "MOVE_EXHAUSTED",
        "market_quality": "MARKET_QUALITY_ACCEPTABLE" if market_quality_score >= 60 else "MARKET_QUALITY_LOW",
    }
    return scores, labels


def evaluate_entry_quality(direction: str, market: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate timing quality for *direction* without changing it.

    The score is the unweighted mean of five 0--100 component scores.  A
    candidate must clear the total threshold and have no weak component.  This
    makes a strong aggregate unable to conceal an exhausted or misaligned entry.
    """
    normalized_direction = str(direction).upper()
    if normalized_direction not in {"BUY", "SELL"}:
        raise ValueError("entry quality requires an existing BUY or SELL direction")

    component_scores, labels = _components(normalized_direction, market)
    entry_score = round(sum(component_scores.values()) / len(component_scores))
    weak_components = [name for name, score in component_scores.items() if score < _MINIMUM_COMPONENT_SCORE]
    accepted = entry_score >= ACCEPTANCE_SCORE and not weak_components
    reasons = [labels[name] for name in component_scores]
    if entry_score < ACCEPTANCE_SCORE:
        reasons.append("ENTRY_SCORE_BELOW_THRESHOLD")
    if weak_components:
        reasons.append("WEAK_COMPONENTS:" + ",".join(weak_components))
    confidence = "HIGH" if entry_score >= 85 else "MEDIUM" if entry_score >= ACCEPTANCE_SCORE else "LOW"
    action = "EXECUTE" if accepted else "WAIT_FOR_BETTER_ENTRY"
    waiting_reason = "NONE" if accepted else ";".join(reasons)
    telemetry = (
        f"ENTRY_QUALITY | direction={normalized_direction} | components="
        f"structure={component_scores['structure']},momentum={component_scores['momentum']},"
        f"location={component_scores['location']},exhaustion={component_scores['exhaustion']},"
        f"market_quality={component_scores['market_quality']} | entry_score={entry_score} | action={action}"
    )
    LOGGER.info(telemetry)
    return {
        "direction": normalized_direction,
        "entry_score": entry_score,
        "accepted": accepted,
        "confidence": confidence,
        "reasons": reasons,
        "component_scores": component_scores,
        "action": action,
        "waiting_reason": waiting_reason,
        "telemetry": telemetry,
    }
