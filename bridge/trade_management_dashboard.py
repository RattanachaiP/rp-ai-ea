"""Runtime Trade Management Dashboard configuration for V27.

This module is intentionally post-entry only.  It loads dashboard/profile JSON
and returns exit-management parameters that the decision engine can publish for
executor-side trade management without changing AI direction, bias, entry, or
market-classification logic.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Mapping

SCHEMA_VERSION = "V27_TRADE_MANAGEMENT_DASHBOARD_SCHEMA_1"
PRODUCTION_PROFILE_FALLBACK_ORDER = ("Profile_A", "Profile_B", "Profile_C", "Profile_D", "Profile_E_SWING_SAFE_SHORT_TP", "Balanced", "Conservative", "Aggressive")
VALIDATION_ONLY_PROFILES = {"TP_ONLY_1USD_TEST"}

DEFAULT_DASHBOARD: Dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "active_profile": "Profile_A",
    "enabled": True,
    "risk": {
        "initial_sl_usd_001_lot": 1.00,
        "dynamic_sl_enabled": True,
        "atr_sl_enabled": False,
        "emergency_sl_usd_001_lot": 1.00,
        "max_floating_loss_usd_001_lot": 0.80,
        "hard_loss_cap_usd_001_lot": 1.00,
        "dynamic_risk_multiplier": 1.0,
    },
    "breakeven": {
        "enable": True,
        "trigger_usd_001_lot": 1.50,
        "offset_usd_001_lot": 0.20,
        "runner_be": False,
        "delay_seconds": 20,
        "minimum_hold_seconds_before_be": 20,
        "minimum_noise_safe_be_usd": 1.20,
        "atr_be_enabled": True,
        "atr_be_multiplier": 1.10,
        "max_spread_points": 35.0,
        "be_lock_distance_usd_001_lot": 0.20,
    },
    "trailing": {
        "enable": True,
        "start_usd_001_lot": 0.80,
        "distance_usd_001_lot": 0.30,
        "step_usd_001_lot": 0.10,
        "atr_trail": False,
        "dynamic_trail": True,
        "structure_trail": True,
    },
    "profit_locks": {
        "enable": True,
        "lock_level_1_usd_001_lot": {"trigger": 0.50, "lock": 0.00},
        "lock_level_2_usd_001_lot": {"trigger": 0.80, "lock": 0.10},
        "lock_level_3_usd_001_lot": {"trigger": 1.20, "lock": 0.40},
        "runner_lock_usd_001_lot": {"trigger": 1.50, "lock": 0.60},
        "minimum_locked_profit_usd_001_lot": 0.05,
    },
    "fixed_take_profit": {
        "enable": False,
        "close_profit_usd_001_lot": 1.00,
        "close_mode": "IMMEDIATE_MARKET_CLOSE",
    },
    "runner": {
        "enable_runner": True,
        "runner_timeout_seconds": 45,
        "momentum_confirmation": True,
        "runner_trail": "STRUCTURE_MOMENTUM_BB_WALK",
        "runner_sl_usd_001_lot": 1.00,
        "runner_exit_mode": "PROTECTED_EXIT_ON_TIMEOUT_OR_MOMENTUM_DECAY",
    },
    "time_exits": {
        "maximum_seconds": 0,
        "maximum_bars": 0,
        "session_exit": False,
        "news_exit": False,
        "position_aging_exit": False,
    },
    "partial_exits": {
        "enable": False,
        "partial_level_1_percent": 0,
        "partial_level_2_percent": 0,
        "partial_level_3_percent": 0,
        "remaining_runner_percent": 100,
    },
    "exit_authority_priority": [
        "EMERGENCY_EXIT",
        "HARD_LOSS_CAP",
        "PROFIT_LOCK",
        "BREAKEVEN",
        "TRAILING",
        "RUNNER",
        "TIME_EXIT",
    ],
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


def dashboard_paths(repo_root: Path) -> Dict[str, Path]:
    return {
        "dashboard": repo_root / "trade_management_dashboard.json",
        "profiles": repo_root / "dashboard_profiles",
    }


def load_trade_management_dashboard(repo_root: Path | None = None) -> Dict[str, Any]:
    root = repo_root or Path(__file__).resolve().parents[1]
    paths = dashboard_paths(root)
    config = copy.deepcopy(DEFAULT_DASHBOARD)
    sources = ["embedded_defaults"]
    warnings = []

    try:
        if paths["dashboard"].exists():
            dashboard_data = _read_json(paths["dashboard"])
            _deep_merge(config, dashboard_data)
            sources.append(str(paths["dashboard"]))
    except Exception as exc:  # config fallback must not stop trading runtime
        warnings.append(f"dashboard_load_failed:{type(exc).__name__}")

    active_profile = str(config.get("active_profile") or "Profile_A")
    if active_profile.upper() in VALIDATION_ONLY_PROFILES:
        warnings.extend([
            "TP_ONLY_PROFILE_DETECTED",
            "TP_ONLY_PRODUCTION_BLOCK",
            "AUTO_FALLBACK_TO_BALANCED",
        ])
        print("TP_ONLY_PROFILE_DETECTED")
        print("TP_ONLY_PRODUCTION_BLOCK")
        print("AUTO_FALLBACK_TO_BALANCED")
        active_profile = next(
            (candidate for candidate in PRODUCTION_PROFILE_FALLBACK_ORDER if (paths["profiles"] / f"{candidate}.json").exists()),
            PRODUCTION_PROFILE_FALLBACK_ORDER[0],
        )
        config["active_profile"] = active_profile

    profile_path = paths["profiles"] / f"{active_profile}.json"
    try:
        if profile_path.exists():
            profile_data = _read_json(profile_path)
            _deep_merge(config, profile_data)
            sources.append(str(profile_path))
    except Exception as exc:  # config fallback must not stop trading runtime
        warnings.append(f"profile_load_failed:{active_profile}:{type(exc).__name__}")

    config["schema_version"] = SCHEMA_VERSION
    config["active_profile"] = str(config.get("active_profile") or active_profile)
    config["decision_engine_freeze"] = "DIRECTION_BIAS_ENTRY_SCORE_INDICATORS_UNCHANGED"
    config["load_sources"] = sources
    config["load_warnings"] = warnings
    config["fallback_defaults_used"] = sources == ["embedded_defaults"] or bool(warnings)
    return config
