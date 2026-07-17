"""Compare replay outcomes for the broker-SL and zero-broker-SL profiles.

This is deliberately evidence-only: profile configuration or a demo payload cannot
be used to infer a trading outcome.  Both CSV inputs must contain closed-trade P/L
before the comparison can reach a conclusion.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

PROFIT_COLUMNS = ("net_profit", "profit", "profit_usd", "realized_profit", "pnl")
DAMAGE_COLUMNS = ("exit_reason", "broker_close_source", "broker_deal_reason", "dashboard_last_close_intent")


def _number(row: dict[str, str], names: Iterable[str]) -> float | None:
    for name in names:
        try:
            value = row.get(name, "").strip()
            if value:
                return float(value)
        except (AttributeError, ValueError):
            continue
    return None


def _damage_bucket(row: dict[str, str]) -> str:
    for name in DAMAGE_COLUMNS:
        value = (row.get(name) or "").strip()
        if value:
            return value.upper()
    return "UNCLASSIFIED_EXIT"


def profile_metrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Return all mandatory comparison metrics from closed realized P/L rows."""
    trades = [(row, value) for row in rows if (value := _number(row, PROFIT_COLUMNS)) is not None]
    if not trades:
        return {
            "available": False,
            "limitation": "No numeric realized P/L column was available; replay profitability was not calculated.",
            "trade_count": 0,
        }

    profits = [value for _, value in trades]
    wins = [value for value in profits if value > 0]
    losses = [value for value in profits if value < 0]
    gross_profit, gross_loss = sum(wins), abs(sum(losses))
    equity = peak = maximum_drawdown = 0.0
    equity_curve: list[float] = []
    damage: dict[str, list[float]] = defaultdict(list)
    for row, profit in trades:
        equity += profit
        peak = max(peak, equity)
        maximum_drawdown = max(maximum_drawdown, peak - equity)
        equity_curve.append(round(equity, 2))
        if profit < 0:
            damage[_damage_bucket(row)].append(profit)

    capital_damage_ranking = sorted(
        (
            {"rank": 0, "exit_bucket": bucket, "loss_count": len(values), "capital_damage": round(abs(sum(values)), 2), "average_loss": round(sum(values) / len(values), 2)}
            for bucket, values in damage.items()
        ),
        key=lambda item: (-item["capital_damage"], item["exit_bucket"]),
    )
    for rank, item in enumerate(capital_damage_ranking, start=1):
        item["rank"] = rank

    return {
        "available": True,
        "trade_count": len(profits),
        "profit_factor": round(gross_profit / gross_loss, 6) if gross_loss else None,
        "expectancy": round(sum(profits) / len(profits), 6),
        "net_profit": round(sum(profits), 2),
        "win_rate": round(len(wins) / len(profits), 6),
        "average_win": round(sum(wins) / len(wins), 6) if wins else 0.0,
        "average_loss": round(sum(losses) / len(losses), 6) if losses else 0.0,
        "maximum_drawdown": round(maximum_drawdown, 2),
        "capital_damage_ranking": capital_damage_ranking,
        "equity_curve": equity_curve,
    }


def compare(baseline: dict[str, Any], zero_broker_sl: dict[str, Any]) -> dict[str, Any]:
    if not baseline["available"] or not zero_broker_sl["available"]:
        return {
            "available": False,
            "conclusion": "INSUFFICIENT_CLOSED_TRADE_EVIDENCE",
            "broker_sl_root_cause": "UNDETERMINED",
            "required_action": "Collect matched closed-trade replay and isolated-demo outcomes for both profiles; do not claim an expectancy effect.",
        }
    delta = round(zero_broker_sl["expectancy"] - baseline["expectancy"], 6)
    improved = delta > 0
    return {
        "available": True,
        "expectancy_delta": delta,
        "expectancy_improved": improved,
        "conclusion": "ZERO_BROKER_SL_IMPROVES_EXPECTANCY" if improved else "ZERO_BROKER_SL_DOES_NOT_IMPROVE_EXPECTANCY",
        "broker_sl_root_cause": "POSSIBLE_CONTRIBUTOR" if improved else "NOT_ROOT_CAUSE",
        "required_action": "Continue only evidence-backed investigation of Broker SL." if improved else "Do not perform further Broker SL-focused work; investigate other ranked capital-damage buckets.",
    }


def demo_contract_validation(repo_root: Path) -> dict[str, Any]:
    """Validate that the configured isolated-demo payload has a literal zero SL."""
    from bridge.v28.clean_core import decide
    from bridge.v28.dashboard_contract import load_dashboard_contract
    from bridge.v28.payload_contract import validate_payload

    dashboard = load_dashboard_contract(repo_root)
    payload = decide({"symbol": "XAUUSD", "price": 2300.0, "buy_score": 7, "sell_score": 3,
                      "sequence_id": 1, "heartbeat_unix": 1, "open_positions": 0,
                      "max_open_positions": 1}, dashboard, now=1)
    valid, reason = validate_payload(payload)
    return {
        "available": True,
        "isolated_demo_only": True,
        "profile": dashboard["active_profile"],
        "broker_sl_required": payload["broker_sl_required"],
        "stop_loss": payload["stop_loss"],
        "payload_contract_valid": valid,
        "payload_contract_reason": reason,
        "passed": valid and not payload["broker_sl_required"] and payload["stop_loss"] == 0.0,
    }


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evidence-only broker-SL replay and isolated-demo comparison.")
    parser.add_argument("--baseline-trades", type=Path, required=True, help="Closed outcomes using the previous Broker-SL profile.")
    parser.add_argument("--zero-broker-sl-trades", type=Path, required=True, help="Closed outcomes using the zero-Broker-SL profile.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = profile_metrics(_read(args.baseline_trades))
    zero = profile_metrics(_read(args.zero_broker_sl_trades))
    report = {
        "report_version": "ZERO_BROKER_SL_VALIDATION_1",
        "baseline_profile": "Profile_F_MARKET_CLOSE_ONLY_WITH_BROKER_SL",
        "zero_broker_sl_profile": "ZERO_BROKER_SL_VALIDATION",
        "replay": {"baseline": baseline, "zero_broker_sl": zero, "comparison": compare(baseline, zero)},
        "demo_contract_validation": demo_contract_validation(args.repo_root),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
