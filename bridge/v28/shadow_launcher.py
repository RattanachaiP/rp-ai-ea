"""Run V28 in shadow mode; this module never invokes an executor or OrderSend."""
from __future__ import annotations

import argparse
from pathlib import Path

from .clean_core import decide, load_market_state, write_decision
from .dashboard_contract import load_dashboard_contract

DEFAULT_SHADOW_PATH = Path(r"RP_AI_EA/shared/XAUUSD/v28_shadow_decision.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish one V28 shadow decision only.")
    parser.add_argument("--market-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_SHADOW_PATH)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    payload = decide(load_market_state(args.market_state), load_dashboard_contract(args.repo_root))
    payload["execution_mode"] = "SHADOW"
    payload["shadow_only"] = True
    payload["ordersend_permitted"] = False
    write_decision(payload, args.output)
    print(f"SHADOW_DECISION_WRITTEN path={args.output} decision={payload['decision']} tier={payload['confidence_tier']}")


if __name__ == "__main__":
    main()
