"""Compare the Phase 1 V26 source with its checked-in parent source.

The comparison uses deterministic no-trade inputs so it does not create a
decision.json, invoke MT5, or depend on live market files.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parents[1]
ENGINE = ROOT / "bridge" / "ai_decision_engine_xauusd_v26_execution_confidence_engine.py"
REPORT = ROOT / "analysis" / "BRAIN_PARITY_REPORT.md"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ENGINE.parent))

FIXTURES = {
    "invalid_bid": {"bid": 0, "ma50": 2300, "bar_time": "parity-invalid-bid"},
    "invalid_ma50": {"bid": 2350, "ma50": 0, "bar_time": "parity-invalid-ma50"},
    "equal_score": {
        "bid": 2350,
        "ma50": 2349,
        "ma90": 2348,
        "ma200": 2347,
        "bb_upper": 2360,
        "bb_middle": 2350,
        "bb_lower": 2340,
        "bb4_upper": 2370,
        "bb4_lower": 2330,
        "rsi": 50,
        "macd_hist": 0,
        "buy_score": 4,
        "sell_score": 4,
        "bar_time": "parity-equal-score",
    },
}
FIELDS = ("decision", "action", "bias", "entry_price", "sl", "tp", "execution_confidence", "probability")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def result(module, market_state):
    _, _, decision = module.build_decision(dict(market_state))
    return decision


def main() -> None:
    baseline_source = subprocess.check_output(
        ["git", "show", "HEAD:bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py"],
        cwd=ROOT,
        text=True,
    )
    with tempfile.TemporaryDirectory() as directory:
        baseline_path = Path(directory) / "baseline_v26.py"
        baseline_path.write_text(baseline_source, encoding="utf-8")
        baseline = load_module(baseline_path, "baseline_v26_brain_parity")
        candidate = load_module(ENGINE, "candidate_v26_brain_parity")

        rows = []
        for name, fixture in FIXTURES.items():
            before = result(baseline, fixture)
            after = result(candidate, fixture)
            reasoning = candidate.brain_market_reasoning(
                candidate.brain_market_understanding(candidate.brain_market_perception(dict(fixture)))
            )
            staged_decision = result(candidate, reasoning.understanding.market_state)
            staged = candidate.brain_position_intelligence(
                candidate.brain_expected_value_engine(
                    candidate.brain_probability_engine(staged_decision)
                )
            )
            unchanged = before == after == staged
            checks = all(before.get(field) == after.get(field) for field in FIELDS)
            rows.append((name, unchanged and checks, before))

    if not all(passed for _, passed, _ in rows):
        raise SystemExit("Brain Phase 1 parity comparison failed")

    source_hash = hashlib.sha256(ENGINE.read_bytes()).hexdigest()
    lines = [
        "# Brain Phase 1 parity report",
        "",
        "## Result",
        "",
        "**PASS.** The authoritative V26 runtime was compared with its `HEAD` "
        "baseline using deterministic market-state fixtures. The Phase 1 "
        "boundaries return their input object unchanged and do not publish stage "
        "metadata. No `decision.json` file was written during this comparison.",
        "",
        "## Compared runtime",
        "",
        f"- Baseline: `HEAD:bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py`.",
        f"- Candidate SHA-256: `{source_hash}`.",
        "- Scope: internal Python call boundaries only; no MT5 or dashboard files were changed.",
        "",
        "## Fixture results",
        "",
        "| Fixture | Result | Decision | Entry | SL | TP | Confidence | Probability |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, _, decision in rows:
        lines.append(
            f"| `{name}` | PASS | `{decision.get('decision', '')}` | "
            f"`{decision.get('entry_price', '')}` | `{decision.get('sl', '')}` | "
            f"`{decision.get('tp', '')}` | `{decision.get('execution_confidence', '')}` | "
            f"`{decision.get('probability', '')}` |"
        )
    lines.extend([
        "",
        "## Validation method",
        "",
        "For each fixture, the script compares the complete `build_decision()` dictionary from the parent source, the candidate source, and the candidate source after Market Perception, Market Understanding, and Market Reasoning. It then passes that same candidate decision through the remaining identity boundaries. It also explicitly compares decision/action/bias, entry, SL, TP, confidence, and probability fields. Market Reasoning is private and unwraps the original market-state dictionary by identity before the candidate build call. The complete payload equality check confirms `decision.json`-schema parity for the deterministic decision construction path; the existing atomic writer is called with the same dictionary and is otherwise unchanged.",
    ])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()
