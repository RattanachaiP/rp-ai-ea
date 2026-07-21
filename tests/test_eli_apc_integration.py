from dataclasses import replace

import pytest

from brain.adaptive_position_construction import PositionBudgetManager, PositionLifecycle, PositionLifecycleManager, PositionLifecycleState
from brain.entry_construction_coordinator import ConstructionAction, EntryConstructionCoordinator, EntryConstructionRequest
from brain.entry_location_intelligence import EntryLocationInput, EntryLocationIntelligence, EntryState


def eli(**changes):
    values = dict(direction="BUY", current_price=4010., swing_high=4100., swing_low=4000., atr=10., recent_impulse_start=4000., recent_impulse_end=4010., pullback_detected=True, pullback_confirmed=True, structure_confirmed=True, liquidity_sweep_up=False, liquidity_sweep_down=False, nearest_support=4005., nearest_resistance=4050., expected_target=4040., invalidation_price=4000., execution_confidence=80.)
    values.update(changes)
    return EntryLocationIntelligence().assess(EntryLocationInput(**values))


def context(existing=False):
    budget = PositionBudgetManager().create(.05, 90)
    lifecycle = PositionLifecycle()
    if existing:
        budget = PositionBudgetManager().allocate(budget, .01)
        lifecycle = PositionLifecycleManager().start_scout(lifecycle)
    return budget, lifecycle


def call(assessment, request):
    budget, lifecycle = context()
    return EntryConstructionCoordinator().decide(assessment, request, lifecycle, budget)

def decide(assessment, existing=False, **request):
    budget, lifecycle = context(existing)
    return EntryConstructionCoordinator().decide(assessment, EntryConstructionRequest("BUY", initial_allocation=.01, **request), lifecycle, budget)


def test_allowed_permits_start_and_apc_scale_only_when_its_rules_pass():
    assert decide(eli()).construction_action is ConstructionAction.ALLOW_START
    assert decide(eli(), True).construction_action is ConstructionAction.HOLD_EXISTING
    allowed_scale = decide(eli(), True, floating_pnl=1., confirmation_event=True)
    assert allowed_scale.construction_action is ConstructionAction.ALLOW_SCALE and allowed_scale.allocation == .025
    assert decide(eli(), True, floating_pnl=0., confirmation_event=True).allocation == 0


@pytest.mark.parametrize("assessment", [
    eli(recent_impulse_end=4021., current_price=4021., expected_target=4050., pullback_detected=False, pullback_confirmed=False),
    eli(pullback_confirmed=False),
    eli(current_price=4090., expected_target=4120.),
    eli(recent_impulse_end=4026., current_price=4026., expected_target=4060., pullback_confirmed=False),
    eli(expected_target=4011.),
    eli(swing_high=4000.),
])
def test_wait_and_all_blocks_prevent_initial_allocation(assessment):
    decision = decide(assessment)
    assert not decision.construction_permission and decision.allocation == 0 and decision.budget_preserved


def test_wait_and_block_remain_distinct_and_preserve_existing_position_and_budget():
    wait = decide(eli(pullback_confirmed=False), True, floating_pnl=1., confirmation_event=True)
    block = decide(eli(current_price=4095., expected_target=4120., execution_confidence=100.), True, floating_pnl=1., confirmation_event=True)
    assert wait.construction_action is ConstructionAction.HOLD_EXISTING
    assert block.construction_action is ConstructionAction.HOLD_EXISTING
    assert wait.eli_entry_state.startswith("WAIT_") and block.eli_entry_state.startswith("BLOCK_")
    assert (wait.budget_total, wait.budget_used, wait.budget_remaining) == (.05, .01, .04)
    assert wait.position_state is block.position_state is PositionLifecycleState.SCOUT_ACTIVE


def test_direction_missing_unknown_and_invalid_budget_fail_safe_deterministically():
    assessment = eli()
    mismatch = call(assessment, EntryConstructionRequest("SELL", .01))
    missing = call(None, EntryConstructionRequest("BUY", .01))
    unknown = replace(assessment, entry_state="UNKNOWN")
    invalid_budget = replace(context()[0], remaining_budget=-.01)
    bad = EntryConstructionCoordinator().decide(assessment, EntryConstructionRequest("BUY", .01), context()[1], invalid_budget)
    for item in (mismatch, missing, call(unknown, EntryConstructionRequest("BUY", .01)), bad):
        assert not item.construction_permission and item.construction_action is ConstructionAction.BLOCK_LOCATION
    assert decide(assessment) == decide(assessment)
