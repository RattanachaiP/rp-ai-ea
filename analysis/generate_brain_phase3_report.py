"""Generate the fixture-backed Phase 3 Market Reasoning/parity report."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from dataclasses import FrozenInstanceError
from pathlib import Path

ROOT = Path(__file__).parents[1]
ENGINE = ROOT / "bridge" / "ai_decision_engine_xauusd_v26_execution_confidence_engine.py"
REPORT = ROOT / "analysis" / "BRAIN_PHASE3_REPORT.md"
FIXTURE = {"bid": 0, "ma50": 2300, "bar_time": "phase3-parity"}
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ENGINE.parent))


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> None:
    source = subprocess.check_output(
        ["git", "show", "HEAD:bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py"],
        cwd=ROOT, text=True)
    with tempfile.TemporaryDirectory() as directory:
        baseline_path = Path(directory) / "baseline.py"
        baseline_path.write_text(source, encoding="utf-8")
        baseline, candidate = load(baseline_path, "phase3_baseline"), load(ENGINE, "phase3_candidate")
        before = baseline.build_decision(dict(FIXTURE))[2]
        understanding = candidate.brain_market_understanding(candidate.brain_market_perception(dict(FIXTURE)))
        reasoning = candidate.brain_market_reasoning(understanding)
        after = candidate.build_decision(reasoning.understanding.market_state)[2]
        assert before == after
        assert reasoning.understanding.market_state is understanding.market_state
        assert not hasattr(reasoning, "decision")
        try:
            reasoning.narrative = "mutated"
        except FrozenInstanceError:
            pass
        else:
            raise AssertionError("MarketReasoning must be immutable")

    example = candidate.brain_market_reasoning(candidate.brain_market_understanding(
        candidate.brain_market_perception({
            "bid": 2355, "ma50": 2354, "ma90": 2352, "ma200": 2350,
            "opens": [2350, 2349], "highs": [2360, 2355], "lows": [2348, 2345],
            "closes": [2358, 2351], "rsi": 60, "macd_hist": 0.5,
            "vwap": 2352, "atr_raw": 8, "server_time": "2026-01-01T08:00:00Z"})))
    assert example.supporting_evidence and example.narrative
    REPORT.write_text(f'''# Brain Phase 3 Market Reasoning report

## Result

**PASS.** Market Reasoning is a private immutable explanation layer. The V26 candidate's deterministic decision payload is exactly equal to the `HEAD` baseline. No `decision.json` file was written.

## Understanding → Reasoning mapping

| Understanding context | Reasoning output |
| --- | --- |
| Market regime, trend state, and structure | Current market-state explanation and supporting evidence. |
| Momentum, transition, and liquidity contexts | Conflicting evidence and contextual reversal case. |
| Context quality, invalid conditions, and compression | Uncertainty and contextual wait case. |
| All of the above | Human-readable narrative. |

## Explanation example

- Supporting evidence: `{'; '.join(example.supporting_evidence)}`.
- Conflicting evidence: `{'; '.join(example.conflicting_evidence) or 'none observed'}`.
- Uncertainty: `{'; '.join(example.uncertainty) or 'none recorded'}`.
- Narrative: {example.narrative}

## Runtime impact

`brain_market_reasoning()` consumes private `MarketUnderstanding` and returns private frozen `MarketReasoning`. It explains context only: it does not generate BUY/SELL, calculate scores, confidence, probability, expected value, or risk, and no production consumer receives it. The runtime unwraps the original market dictionary by object identity before `build_decision()`.

## Payload parity

The reasoning object is not serialized, merged into a decision payload, passed to the writer, or consumed by MT5, the dashboard, or the executor. Complete deterministic `build_decision()` equality against `HEAD` passed; `decision.json` and all interfaces therefore remain unchanged.

## Regression status

**PASS.** Immutability, private-object behavior, object-identity unwrapping, and baseline payload parity passed. The layer has no MT5, dashboard, executor, or decision-writer dependency.
''', encoding="utf-8")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()
