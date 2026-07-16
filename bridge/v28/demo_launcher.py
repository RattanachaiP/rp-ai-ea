"""Prepare a V28 demo-only decision feed; no live path is selected by default."""
from __future__ import annotations

import argparse
from pathlib import Path

from .clean_core import decide, load_market_state, write_decision
from .dashboard_contract import load_dashboard_contract


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a V28 payload for an isolated demo terminal.")
    parser.add_argument("--market-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--demo-confirmation", action="store_true", help="Required to emit a demo-executable payload.")
    args = parser.parse_args()
    if not args.demo_confirmation:
        parser.error("--demo-confirmation is required; V28 cannot be launched to an unspecified environment")
    payload = decide(load_market_state(args.market_state), load_dashboard_contract(args.repo_root))
    payload["execution_mode"] = "ISOLATED_DEMO"
    payload["live_execution_permitted"] = False
    write_decision(payload, args.output)
    print(f"DEMO_DECISION_WRITTEN path={args.output} decision={payload['decision']} tier={payload['confidence_tier']}")


if __name__ == "__main__":
    main()
