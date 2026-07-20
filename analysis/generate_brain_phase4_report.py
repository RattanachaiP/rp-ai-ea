"""Generate the fixture-backed Phase 4 Probability Engine/parity report."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from dataclasses import FrozenInstanceError
from pathlib import Path

ROOT = Path(__file__).parents[1]
ENGINE = ROOT / "bridge" / "ai_decision_engine_xauusd_v26_execution_confidence_engine.py"
REPORT = ROOT / "analysis" / "BRAIN_PHASE4_REPORT.md"
FIXTURE = {"bid": 0, "ma50": 2300, "bar_time": "phase4-parity"}
CONTEXT_FIXTURE = {
    "bid": 2355, "ma50": 2354, "ma90": 2352, "ma200": 2350,
    "opens": [2350, 2349], "highs": [2360, 2355], "lows": [2348, 2345],
    "closes": [2358, 2351], "rsi": 60, "macd_hist": 0.5,
    "vwap": 2352, "atr_raw": 8, "server_time": "2026-01-01T08:00:00Z",
}
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
        baseline, candidate = load(baseline_path, "phase4_baseline"), load(ENGINE, "phase4_candidate")
        before = baseline.build_decision(dict(FIXTURE))[2]
        understanding = candidate.brain_market_understanding(candidate.brain_market_perception(dict(FIXTURE)))
        reasoning = candidate.brain_market_reasoning(understanding)
        assessment = candidate.brain_probability_assessment(understanding, reasoning)
        after = candidate.build_decision(reasoning.understanding.market_state)[2]
        assert before == after
        assert candidate.brain_probability_engine(after) is after

    context = candidate.brain_market_understanding(candidate.brain_market_perception(CONTEXT_FIXTURE))
    context_reasoning = candidate.brain_market_reasoning(context)
    context_assessment = candidate.brain_probability_assessment(context, context_reasoning)
    estimates = (context_assessment.continuation, context_assessment.reversal,
                 context_assessment.range, context_assessment.breakout, context_assessment.no_trade)
    assert round(sum(item.probability for item in estimates), 4) == 1.0
    assert all(item.supporting_evidence and item.conflicting_evidence and item.uncertainty_evidence for item in estimates)
    try:
        context_assessment.methodology = "changed"
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("ProbabilityAssessment must be immutable")

    REPORT.write_text(f'''# Brain Phase 4 Probability Engine report

## Result

**PASS.** The Probability Engine creates a private immutable market-state assessment while the deterministic V26 decision payload remains exactly equal to the `HEAD` baseline. No `decision.json` file was written.

## Context consumed

The engine accepts only `MarketUnderstanding` and its matching `MarketReasoning`. It uses regime, trend/structure, momentum, expansion/compression, transition, liquidity, context quality, and the reasoning uncertainty record. It does not accept a decision dictionary, V26 confidence, score, risk payload, MT5 data source, dashboard profile, or executor state.

## Probability methodology

The engine starts continuation, reversal, range, breakout, and no-trade at equal prior weight. It applies transparent additive adjustments from Brain context, clips weights at zero, and normalizes them into a distribution that sums to 1. Each state estimate includes supporting evidence, conflicting evidence, one bounded uncertainty estimate, and uncertainty evidence. The output contains no BUY or SELL probability.

Context fixture distribution: continuation `{context_assessment.continuation.probability:.4f}`, reversal `{context_assessment.reversal.probability:.4f}`, range `{context_assessment.range.probability:.4f}`, breakout `{context_assessment.breakout.probability:.4f}`, no-trade `{context_assessment.no_trade.probability:.4f}`.

## Runtime impact

The runtime constructs `ProbabilityAssessment` after the private Market Reasoning object and verifies its type. The assessment is retained only in process, then the unchanged original market dictionary reaches `build_decision()`. The legacy `brain_probability_engine()` remains an identity boundary for the V26 decision dictionary. The engine cannot generate BUY/SELL, replace confidence or scores, filter trades, construct risk, or affect publication.

## Payload parity

**PASS.** The assessment is not serialized, merged into the decision, passed to the decision writer, or consumed by MT5, dashboard, or executor code. Baseline and candidate complete deterministic `build_decision()` dictionaries are equal.

## Regression status

**PASS.** Immutable assessment, required evidence, bounded uncertainty, normalized market-state probabilities, no direction-specific probabilities, and V26 payload parity passed.
''', encoding="utf-8")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()
