"""Generate the fixture-backed Phase 2A perception/parity report."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[1]
ENGINE = ROOT / "bridge" / "ai_decision_engine_xauusd_v26_execution_confidence_engine.py"
REPORT = ROOT / "analysis" / "BRAIN_PHASE2A_REPORT.md"
FIXTURE = {"bid": 0, "ma50": 2300, "bar_time": "phase2a-parity"}
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
        baseline, candidate = load(baseline_path, "phase2a_baseline"), load(ENGINE, "phase2a_candidate")
        assert baseline.build_decision(dict(FIXTURE))[2] == candidate.build_decision(dict(FIXTURE))[2]
    perception = candidate.brain_market_perception({
        "bid": 2355, "ma50": 2354, "ma90": 2352, "ma200": 2350,
        "opens": [2350, 2349], "highs": [2360, 2355], "lows": [2348, 2345], "closes": [2358, 2351],
        "rsi": 60, "macd_hist": 0.5, "vwap": 2352, "atr_raw": 8, "server_time": "2026-01-01T08:00:00Z"})
    assert candidate.brain_market_understanding(perception).market_state is perception.market_state
    assert not hasattr(perception, "decision")
    REPORT.write_text("""# Brain Phase 2A Market Perception report

## Result

**PASS.** Market Perception is now a private, observation-only object. A deterministic V26 candidate decision is exactly equal to the `HEAD` baseline. No `decision.json` file was written.

## Extracted observations

| Observation | Extraction |
| --- | --- |
| Trend | Ordered MA50/MA90/MA200. |
| Swing High / Low | Candle-series extrema. |
| Market Structure | Higher-high/higher-low or lower-high/lower-low candle progression. |
| Liquidity Sweep | Breach and close back through a prior candle extreme. |
| Volatility | Current versus average candle range. |
| ATR State | Raw ATR telemetry availability only. |
| VWAP Relation | Bid above, below, or at supplied VWAP. |
| Session | UTC descriptive session from market timestamp. |
| Momentum Observation | RSI/MACD alignment. |
| Compression / Expansion | BB width and candle-range observation. |
| Impulse Detection | Current candle body-to-range observation. |

## Mapping

`read_market()` dictionary → `brain_market_perception()` → private `MarketPerception` → `brain_market_understanding()` → exact original dictionary → existing `build_decision()` path. The object is not serialized or merged into the candidate decision.

## Runtime impact

The layer does not choose an action, calculate a trade score, or determine BUY/SELL. It has no MT5, dashboard, executor, writer, or `decision.json` dependency. Existing V26 logic receives the original dictionary by object identity after Market Understanding.

## Parity verification

The generator compared complete `build_decision()` dictionaries for a deterministic invalid-bid fixture against `HEAD`; they were equal. It also verified perception-object unwrapping returns the original market-state object and that the object has no decision field.
""", encoding="utf-8")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()
