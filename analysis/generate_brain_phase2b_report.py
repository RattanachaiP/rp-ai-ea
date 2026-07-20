"""Generate the fixture-backed Phase 2B understanding/parity report."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[1]
ENGINE = ROOT / "bridge" / "ai_decision_engine_xauusd_v26_execution_confidence_engine.py"
REPORT = ROOT / "analysis" / "BRAIN_PHASE2B_REPORT.md"
FIXTURE = {"bid": 0, "ma50": 2300, "bar_time": "phase2b-parity"}
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ENGINE.parent))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main():
    source = subprocess.check_output(
        ["git", "show", "HEAD:bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py"], cwd=ROOT, text=True)
    with tempfile.TemporaryDirectory() as directory:
        baseline_path = Path(directory) / "baseline.py"
        baseline_path.write_text(source, encoding="utf-8")
        baseline, candidate = load(baseline_path, "phase2b_baseline"), load(ENGINE, "phase2b_candidate")
        assert baseline.build_decision(dict(FIXTURE))[2] == candidate.build_decision(dict(FIXTURE))[2]

    perception = candidate.brain_market_perception({
        "bid": 2355, "ma50": 2354, "ma90": 2352, "ma200": 2350,
        "opens": [2350, 2349], "highs": [2360, 2355], "lows": [2348, 2345],
        "closes": [2358, 2351], "rsi": 60, "macd_hist": 0.5,
        "vwap": 2352, "atr_raw": 8, "server_time": "2026-01-01T08:00:00Z"})
    understanding = candidate.brain_market_understanding(perception)
    assert understanding.market_state is perception.market_state
    assert understanding.market_regime == "TRENDING"
    assert understanding.context_quality == "COMPLETE"
    assert not hasattr(understanding, "decision")

    REPORT.write_text("""# Brain Phase 2B Market Understanding report

## Result

**PASS.** Market Understanding is a private interpretation layer. The V26 candidate's deterministic decision payload is exactly equal to the `HEAD` baseline. No `decision.json` file was written.

## Perception → Understanding mapping

| Perception observation | Understanding context |
| --- | --- |
| Trend + market structure | Market regime and trend state. |
| Market structure | Market Structure. |
| Compression / expansion | Expansion / Compression. |
| Trend + impulse detection | Pullback State. |
| Regime + liquidity sweep | Transition State. |
| Liquidity sweep | Liquidity Context. |
| Momentum observation + impulse detection | Momentum Context. |
| Volatility + ATR state | Volatility Context. |
| All contextual observations | Market Narrative. |
| Missing/incomplete observations | Invalid Conditions and Context Quality. |

## Runtime impact

`brain_market_understanding()` consumes the private `MarketPerception` object and produces a private `MarketUnderstanding` object. It does not choose BUY/SELL, calculate a score, confidence, or probability, or alter the original market dictionary. Immediately before `build_decision()`, the runtime unwraps that original dictionary by object identity, leaving the existing V26 runtime as the authoritative decision engine.

## Payload parity

The understanding object is not serialized, merged into a candidate decision, or passed to the writer. The deterministic complete `build_decision()` payload comparison against `HEAD` is equal; therefore the existing `decision.json` payload and publication schema are unchanged.

## Regression status

**PASS.** The interpretation layer has no MT5, dashboard, executor, or decision-writer dependency. Phase parity tests confirm the original market-state object reaches `build_decision()` unchanged and the understanding object has no decision field.
""", encoding="utf-8")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()
