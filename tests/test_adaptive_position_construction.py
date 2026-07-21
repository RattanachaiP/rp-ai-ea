from brain.adaptive_position_construction import (
    PositionBudgetManager, PositionLifecycle, PositionLifecycleManager,
    PositionLifecycleState, ScalingDecisionEngine,
)


def test_apc_constructs_from_budget_and_scales_only_winning_event_driven_positions():
    budgets = PositionBudgetManager()
    lifecycle_manager = PositionLifecycleManager()
    engine = ScalingDecisionEngine()
    budget = budgets.create(1.0, 82)
    budget = budgets.allocate(budget, 0.25)  # Scout allocation.
    lifecycle = lifecycle_manager.start_scout(PositionLifecycle())

    rejected = engine.decide(budget, lifecycle, floating_pnl=1.0)
    assert not rejected.approved and rejected.reason == "NO_QUALIFYING_MARKET_EVENT"
    loser = engine.decide(budget, lifecycle, floating_pnl=0.0, confirmation_event=True)
    assert not loser.approved and loser.reason == "WINNER_ONLY_SCALING"

    decision = engine.decide(budget, lifecycle, floating_pnl=1.0, confirmation_event=True)
    assert decision.approved and decision.allocation == 0.5
    budget = budgets.allocate(budget, decision.allocation)
    lifecycle = lifecycle_manager.apply_scaling(lifecycle, decision)
    assert budget.remaining_budget == 0.25
    assert lifecycle.state is PositionLifecycleState.CONFIRMATION_ELIGIBLE


def test_apc_refreshes_confidence_and_cancels_uncommitted_budget_on_invalidation():
    budgets = PositionBudgetManager()
    lifecycle_manager = PositionLifecycleManager()
    engine = ScalingDecisionEngine()
    budget = budgets.allocate(budgets.create(1.0, 90), 0.25)
    lifecycle = lifecycle_manager.start_scout(PositionLifecycle())
    budget = budgets.refresh_confidence(budget, 45)
    low_confidence = engine.decide(budget, lifecycle, floating_pnl=1.0, confirmation_event=True)
    assert not low_confidence.approved
    assert low_confidence.reason == "CONFIDENCE_REFRESH_BELOW_CONFIRMATION_THRESHOLD"

    cancellation = engine.decide(budget, lifecycle, floating_pnl=1.0, invalidation_event=True)
    budget = budgets.cancel_remaining(budget)
    lifecycle = lifecycle_manager.cancel_remaining(lifecycle, cancellation.reason)
    assert budget.remaining_budget == 0 and budget.cancelled_budget == 0.75
    assert lifecycle.state is PositionLifecycleState.REMAINING_BUDGET_CANCELLED


def test_apc_has_no_time_based_input_or_transition():
    assert "time" not in ScalingDecisionEngine.decide.__annotations__
    assert not any("time" in name.lower() for name in PositionLifecycleManager.__dict__)
