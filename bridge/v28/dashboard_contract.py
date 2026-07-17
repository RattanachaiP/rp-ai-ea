"""V28 dashboard contract loader.

Dashboard owns all post-entry trade management parameters.  This module only
loads and normalizes that contract for publication; it does not decide entries.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Mapping

SCHEMA_VERSION = "V28_DASHBOARD_CONTRACT_1"

DEFAULT_DASHBOARD: Dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "trade_enabled": True,
    "active_profile": "Profile_F_MARKET_CLOSE_ONLY",
    "validation_baseline_profile": "Profile_F_MARKET_CLOSE_ONLY",
    "management_mode": "DASHBOARD_MANAGED",
    "fixed_tp": {"enabled": True, "points": 100.0},
    "broker_sl": {"enabled": False, "points": 0.0},
    "breakeven": {"enabled": False, "trigger_points": 0.0, "offset_points": 0.0},
    "trailing": {"enabled": False, "start_points": 0.0, "distance_points": 0.0, "step_points": 0.0},
    "profit_lock": {"enabled": False, "levels": []},
    "runner": {"enabled": False, "timeout_seconds": 0},
    "emergency": {"close_all": False, "entries_disabled": False},
    "time_exit": {"enabled": False, "maximum_seconds": 0},
    "partial_close": {"enabled": False, "levels": []},
    "risk_hard_loss_cap_usd_per_001_lot": 1.2,
    "fixed_tp_close_usd_per_001_lot": 1.0,
    "scaling": {"enabled": False},
    "pyramiding": {"enabled": False},
}


def _deep_merge(base: Dict[str, Any], overlay: Mapping[str, Any]) -> Dict[str, Any]:
    for key, value in overlay.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def load_dashboard_contract(repo_root: Path | None = None) -> Dict[str, Any]:
    root = repo_root or Path(__file__).resolve().parents[2]
    cfg = copy.deepcopy(DEFAULT_DASHBOARD)
    sources = ["embedded_v28_defaults"]
    warnings: list[str] = []

    dashboard_path = root / "trade_management_dashboard_v28.json"
    try:
        if dashboard_path.exists():
            _deep_merge(cfg, _read_json(dashboard_path))
            sources.append(str(dashboard_path))
    except Exception as exc:  # dashboard load failure must be visible, not fatal
        warnings.append(f"dashboard_load_failed:{type(exc).__name__}")

    profile = str(cfg.get("active_profile") or "Balanced")
    profile_path = root / "dashboard_profiles" / f"{profile}_v28.json"
    try:
        if profile_path.exists():
            _deep_merge(cfg, _read_json(profile_path))
            sources.append(str(profile_path))
    except Exception as exc:
        warnings.append(f"profile_load_failed:{profile}:{type(exc).__name__}")

    cfg["schema_version"] = SCHEMA_VERSION
    cfg["active_profile"] = str(cfg.get("active_profile") or profile)
    cfg["validation_baseline_profile"] = "Profile_F_MARKET_CLOSE_ONLY"
    cfg["load_sources"] = sources
    cfg["load_warnings"] = warnings
    cfg["fallback_defaults_used"] = sources == ["embedded_v28_defaults"] or bool(warnings)
    return cfg
