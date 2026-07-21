from dataclasses import replace

from brain.adaptive_position_construction import PositionBudgetManager, PositionLifecycle
from brain.decision_pipeline import DecisionPackage, DecisionPipeline, DecisionPipelineInput
from brain.entry_construction_coordinator import EntryConstructionCoordinator, EntryConstructionRequest
from brain.entry_location_intelligence import EntryLocationInput, EntryLocationIntelligence
from brain.expected_value_engine import evaluate_expected_value
from brain.market_perception import extract_market_perception
from brain.market_reasoning import reason_about_market
from brain.market_understanding import interpret_market_understanding
from brain.probability_engine import estimate_market_probabilities


def pipeline_input():
    understanding = interpret_market_understanding(extract_market_perception({
        "bid": 2355, "ma50": 2354, "ma90": 2352, "ma200": 2350,
        "opens": [2350, 2349], "highs": [2360, 2355], "lows": [2348, 2345],
        "closes": [2358, 2351], "rsi": 60, "macd_hist": 0.5, "atr_raw": 8,
    }))
    return DecisionPipelineInput(
        understanding, reason_about_market(understanding),
        EntryLocationInput("BUY", 4010., 4100., 4000., 10., 4000., 4010., True, True,
                           True, False, False, 4005., 4050., 4040., 4000., 80.),
        EntryConstructionRequest("BUY", initial_allocation=.01), PositionLifecycle(),
        PositionBudgetManager().create(.05, 90),
    )


def test_pipeline_orders_modules_and_composes_valid_decision_package():
    calls = []

    def probability(understanding, reasoning):
        calls.append("Probability")
        return estimate_market_probabilities(understanding, reasoning)

    def expected_value(understanding, reasoning, probabilities):
        calls.append("ExpectedValue")
        return evaluate_expected_value(understanding, reasoning, probabilities)

    class Location(EntryLocationIntelligence):
        def assess(self, value):
            calls.append("ELI")
            return super().assess(value)

    class Coordinator(EntryConstructionCoordinator):
        def decide(self, *args):
            calls.append("Coordinator/APC")
            return super().decide(*args)

    result = DecisionPipeline(probability_estimator=probability, expected_value_evaluator=expected_value,
                              location_intelligence=Location(), construction_coordinator=Coordinator()).decide(pipeline_input())

    assert calls == ["Probability", "ExpectedValue", "ELI", "Coordinator/APC"]
    assert isinstance(result, DecisionPackage)
    assert result.direction == "BUY" and result.decision == "TRADE"
    assert result.entry_permission and result.entry_state == "ENTRY_ALLOWED"
    assert result.construction_action == "ALLOW_START"
    assert (result.position_budget_total, result.position_budget_used, result.position_budget_remaining) == (.05, 0., .05)


def test_trace_is_complete_ordered_and_deterministic():
    pipeline = DecisionPipeline()
    first, second = pipeline.decide(pipeline_input()), pipeline.decide(pipeline_input())

    assert first == second
    assert first.decision_trace == (
        "Probability=0.5000", "ExpectedValue=0.3750", "ELI=ENTRY_ALLOWED",
        "Coordinator=ALLOW_START", "APC=BudgetPreserved",
    )


def test_wait_location_is_composed_without_overriding_eli_or_apc_ownership():
    data = pipeline_input()
    waiting = replace(data, location_input=replace(data.location_input, pullback_confirmed=False))
    result = DecisionPipeline().decide(waiting)

    assert result.decision == "WAIT"
    assert result.entry_state == "WAIT_CONFIRMATION"
    assert result.construction_action == "WAIT_LOCATION"
    assert result.position_budget_used == 0. and result.position_budget_remaining == .05


def test_module_failure_is_fail_safe_wait():
    def broken(*_args):
        raise RuntimeError("probability unavailable")

    result = DecisionPipeline(probability_estimator=broken).decide(pipeline_input())
    assert result.decision == "WAIT"
    assert result.decision_trace == ("FAIL_SAFE=RuntimeError:probability unavailable",)
    assert not result.entry_permission and result.construction_action == "NO_ACTION"


def test_invalid_module_output_is_fail_safe_wait():
    result = DecisionPipeline(probability_estimator=lambda *_args: object()).decide(pipeline_input())
    assert result.decision == "WAIT"
    assert result.decision_trace == ("FAIL_SAFE=TypeError:INVALID_PROBABILITY_OUTPUT",)
