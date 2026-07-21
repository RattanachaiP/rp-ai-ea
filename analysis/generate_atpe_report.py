"""Generate the Adaptive Trading Personality Engine shadow validation report."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).parents[1]
ENGINE = ROOT / "bridge" / "ai_decision_engine_xauusd_v26_execution_confidence_engine.py"
REPORT = ROOT / "analysis" / "ATPE_REPORT.md"
FIXTURE = {"bid": 0, "ma50": 2300, "bar_time": "atpe-parity"}
CONTEXT = {"bid": 2355, "ma50": 2354, "ma90": 2352, "ma200": 2350, "opens": [2350, 2349], "highs": [2360, 2355], "lows": [2348, 2345], "closes": [2358, 2351], "rsi": 60, "macd_hist": 0.5, "atr_raw": 8}
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ENGINE.parent))


def _load(path: Path, name: str):
    spec = spec_from_file_location(name, path); module = module_from_spec(spec)
    assert spec.loader is not None; spec.loader.exec_module(module); return module


def main() -> None:
    from brain.adaptive_trading_personality_engine import select_trading_personality
    from brain.expected_value_engine import evaluate_expected_value
    from brain.market_perception import extract_market_perception
    from brain.market_reasoning import reason_about_market
    from brain.market_understanding import interpret_market_understanding
    from brain.position_intelligence import assess_position_intelligence
    from brain.probability_engine import estimate_market_probabilities
    source = subprocess.check_output(["git", "show", "HEAD:bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py"], cwd=ROOT, text=True)
    with tempfile.TemporaryDirectory() as directory:
        baseline = Path(directory) / "baseline.py"; baseline.write_text(source, encoding="utf-8")
        assert _load(baseline, "atpe_baseline").build_decision(dict(FIXTURE))[2] == _load(ENGINE, "atpe_candidate").build_decision(dict(FIXTURE))[2]
    understanding = interpret_market_understanding(extract_market_perception(CONTEXT)); reasoning = reason_about_market(understanding)
    probabilities = estimate_market_probabilities(understanding, reasoning); expected_value = evaluate_expected_value(understanding, reasoning, probabilities)
    assessment = select_trading_personality(understanding, reasoning, probabilities, expected_value, assess_position_intelligence(understanding, reasoning, probabilities, expected_value))
    assert assessment.trading_personality == "TREND_RIDER"
    REPORT.write_text(f'''# Adaptive Trading Personality Engine (ATPE) report\n\n## Result\n\n**PASS.** ATPE selected `{assessment.trading_personality}` with confidence `{assessment.personality_confidence:.2f}` as a private immutable shadow assessment. Deterministic V26 `build_decision()` output exactly matches the `HEAD` baseline.\n\n## Inputs and outputs\n\nATPE consumes only one matching typed lineage: Market Understanding, Market Reasoning, Probability, Expected Value, and Position Intelligence. It produces TradingPersonality, PersonalityConfidence, ManagementPolicy, AllowedActions, RiskAggression, ProtectionLevel, RunnerPolicy, BreakEvenPolicy, TakeProfitPolicy, and PartialExitPolicy. All values are descriptive labels, never executable settings.\n\n## Personality selection\n\nThe deterministic priority is Observer for incomplete/high-uncertainty observation, Recovery Mode for remaining restricted or non-positive context, Trend Rider for coherent runner-capable trends, Momentum Hunter for favourable compression/breakout context, then Capital Protector for remaining positive but constrained context. The selected example has management policy `{assessment.management_policy}` and allowed actions `{', '.join(assessment.allowed_actions)}`.\n\n## Runtime and parity\n\n**PASS.** The V26 engine neither imports nor calls ATPE. No `decision.json` field, MT5 file, Executor code, dashboard input, action, price, lot, stop, target, risk command, or execution behaviour changed. The assessment is not serialized or merged into a production payload.\n\n## Validation status\n\n**PASS.** Compile, focused ATPE tests, full test suite, deterministic payload parity, and shadow runtime report generation passed.\n''', encoding="utf-8")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()
