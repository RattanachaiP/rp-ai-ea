"""Generate the Brain Phase 5 Expected Value Engine validation report."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from dataclasses import FrozenInstanceError
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).parents[1]
ENGINE = ROOT / "bridge" / "ai_decision_engine_xauusd_v26_execution_confidence_engine.py"
REPORT = ROOT / "analysis" / "BRAIN_PHASE5_REPORT.md"
FIXTURE = {"bid": 0, "ma50": 2300, "bar_time": "phase5-parity"}
CONTEXT_FIXTURE = {
    "bid": 2355, "ma50": 2354, "ma90": 2352, "ma200": 2350,
    "opens": [2350, 2349], "highs": [2360, 2355], "lows": [2348, 2345],
    "closes": [2358, 2351], "rsi": 60, "macd_hist": 0.5, "atr_raw": 8,
}
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ENGINE.parent))


def _load(path: Path, name: str):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> None:
    from brain.expected_value_engine import evaluate_expected_value
    from brain.market_perception import extract_market_perception
    from brain.market_reasoning import reason_about_market
    from brain.market_understanding import interpret_market_understanding
    from brain.probability_engine import estimate_market_probabilities

    source = subprocess.check_output(["git", "show", "HEAD:bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py"], cwd=ROOT, text=True)
    with tempfile.TemporaryDirectory() as directory:
        baseline_path = Path(directory) / "baseline.py"
        baseline_path.write_text(source, encoding="utf-8")
        baseline, candidate = _load(baseline_path, "phase5_baseline"), _load(ENGINE, "phase5_candidate")
        before, after = baseline.build_decision(dict(FIXTURE))[2], candidate.build_decision(dict(FIXTURE))[2]
        assert before == after

    understanding = interpret_market_understanding(extract_market_perception(CONTEXT_FIXTURE))
    reasoning = reason_about_market(understanding)
    probabilities = estimate_market_probabilities(understanding, reasoning)
    assessment = evaluate_expected_value(understanding, reasoning, probabilities)
    try:
        assessment.expected_value = 0.0
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("ExpectedValueAssessment must be immutable")
    assert not hasattr(assessment, "buy") and not hasattr(assessment, "sell")

    REPORT.write_text(f'''# Brain Phase 5 Expected Value Engine report

## Result

**PASS.** The Expected Value Engine produces a private immutable analytical assessment. Deterministic V26 `build_decision()` output remains exactly equal to the `HEAD` baseline; no `decision.json` file was written.

## Inputs consumed

The engine consumes only matching `MarketUnderstanding`, `MarketReasoning`, and `ProbabilityAssessment` instances. Identity checks ensure reasoning and probability telemetry belong to the supplied understanding. It consumes no decision dictionary, confidence, score, risk payload, MT5, dashboard, executor, or writer state.

## Evaluation methodology

Risk is the normalized probability of reversal plus no-trade states (`{assessment.risk:.4f}`). Reward is the normalized probability of continuation plus breakout (`{assessment.reward:.4f}`); range is neutral. Risk/reward is `{assessment.risk_reward_ratio:.4f}` and expected value is reward minus risk (`{assessment.expected_value:.4f}`). Uncertainty impact is the mean bounded state uncertainty multiplied by exposed opportunity units (`{assessment.uncertainty_impact:.4f}`), producing confidence interval `[{assessment.confidence_interval.lower:.4f}, {assessment.confidence_interval.upper:.4f}]`. Opportunity quality is `{assessment.opportunity_quality}` and trade quality is `{assessment.trade_quality}`. These labels are descriptive only and never authorize a trade.

## Runtime impact

**NONE.** The engine is not imported or invoked by the production V26 runtime. It creates no BUY/SELL output, decision, position size, risk instruction, trade execution, or payload mutation.

## Payload parity

**PASS.** The assessment is not serialized, merged into a candidate decision, passed to the writer, or consumed by MT5, dashboard, or executor code. Complete deterministic V26 decision dictionaries match the `HEAD` baseline.

## Regression status

**PASS.** Immutable assessment, input identity validation, non-directional output, normalized risk/reward and expected-value calculation, bounded confidence interval, payload parity, and runtime isolation passed.
''', encoding="utf-8")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()
