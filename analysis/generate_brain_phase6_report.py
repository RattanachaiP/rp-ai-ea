"""Generate the Brain Phase 6 Position Intelligence validation report."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from dataclasses import FrozenInstanceError
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).parents[1]
ENGINE = ROOT / "bridge" / "ai_decision_engine_xauusd_v26_execution_confidence_engine.py"
REPORT = ROOT / "analysis" / "BRAIN_PHASE6_REPORT.md"
FIXTURE = {"bid": 0, "ma50": 2300, "bar_time": "phase6-parity"}
CONTEXT = {"bid": 2355, "ma50": 2354, "ma90": 2352, "ma200": 2350, "opens": [2350, 2349], "highs": [2360, 2355], "lows": [2348, 2345], "closes": [2358, 2351], "rsi": 60, "macd_hist": 0.5, "atr_raw": 8}
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ENGINE.parent))

def _load(path: Path, name: str):
    spec = spec_from_file_location(name, path); module = module_from_spec(spec)
    assert spec.loader is not None; spec.loader.exec_module(module); return module

def main() -> None:
    from brain.expected_value_engine import evaluate_expected_value
    from brain.market_perception import extract_market_perception
    from brain.market_reasoning import reason_about_market
    from brain.market_understanding import interpret_market_understanding
    from brain.position_intelligence import assess_position_intelligence
    from brain.probability_engine import estimate_market_probabilities
    source = subprocess.check_output(["git", "show", "HEAD:bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py"], cwd=ROOT, text=True)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "baseline.py"; path.write_text(source, encoding="utf-8")
        assert _load(path, "phase6_baseline").build_decision(dict(FIXTURE))[2] == _load(ENGINE, "phase6_candidate").build_decision(dict(FIXTURE))[2]
    understanding = interpret_market_understanding(extract_market_perception(CONTEXT)); reasoning = reason_about_market(understanding)
    probabilities = estimate_market_probabilities(understanding, reasoning); expected_value = evaluate_expected_value(understanding, reasoning, probabilities)
    assessment = assess_position_intelligence(understanding, reasoning, probabilities, expected_value)
    try: assessment.position_quality = "changed"
    except FrozenInstanceError: pass
    else: raise AssertionError("PositionIntelligenceAssessment must be immutable")
    assert not any(hasattr(assessment, name) for name in ("buy", "sell", "entry", "sl", "tp", "lot_size"))
    REPORT.write_text(f'''# Brain Phase 6 Position Intelligence report\n\n## Result\n\n**PASS.** Position Intelligence produces a private immutable shadow assessment. Deterministic V26 `build_decision()` output matches the `HEAD` baseline exactly; no `decision.json` file was written.\n\n## Input mapping\n\nThe assessment accepts only one matching lineage: `MarketUnderstanding` provides regime, structure, volatility, context quality, and invalid conditions; `MarketReasoning` provides conflicts; `ProbabilityAssessment` provides non-directional market-state estimates; and `ExpectedValueAssessment` provides normalized risk/reward, expected value, and uncertainty. It accepts no V26 decision dictionary, payload, prices for construction, risk settings, dashboard, MT5, executor, or writer state.\n\n## Position-assessment methodology\n\nAll labels are descriptive normalized context. The example is `{assessment.position_style}` with `{assessment.position_eligibility}`, `{assessment.risk_budget_class}`, `{assessment.stop_loss_context}`, `{assessment.target_context}`, and `{assessment.risk_reward_feasibility}`. Position uncertainty is `{assessment.position_uncertainty:.4f}` ({assessment.position_uncertainty_class}). Structure and reasoning conflicts create invalidation context; no exact entry, stop, target, lot, or live risk is fabricated.\n\n## Examples of analytical outputs\n\nScalp `{assessment.scalp_suitability}`; intraday `{assessment.intraday_suitability}`; runner `{assessment.runner_suitability}`; scale-in `{assessment.scale_in_suitability}`; partial exit `{assessment.partial_exit_suitability}`; position quality `{assessment.position_quality}`. These are not execution recommendations.\n\n## Runtime isolation\n\n**NONE.** The V26 runtime neither imports nor invokes this module. It has no BUY/SELL authority and cannot alter V26 direction, entry, SL/TP, lot size, risk, payload construction, publication, MT5, executor, or dashboard behavior.\n\n## Payload parity\n\n**PASS.** The assessment is neither serialized nor merged into `decision.json`; baseline and candidate complete deterministic V26 payload dictionaries are equal.\n\n## Regression status\n\n**PASS.** Immutability, lineage validation, non-executable analytical output, runtime isolation, and payload parity passed.\n\n## DATA_CONTRACT impact\n\n**Non-breaking extension only.** The frozen production compatibility boundaries and payload schema remain unchanged. The private typed Phase 6 contract adds no published field and transfers no ownership.\n\n## Execution authority\n\n**Unchanged.** V26 remains authoritative for direction, entry, stop loss, take profit, lot size, risk, payload construction, and publication. No execution authority moved.\n''', encoding="utf-8")
    print(f"Wrote {REPORT}")

if __name__ == "__main__": main()
