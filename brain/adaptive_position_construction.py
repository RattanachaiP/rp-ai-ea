"""Adaptive Position Construction (APC) Phase 1 domain model.

APC is an in-memory post-entry construction policy.  It replaces a fixed
``target lot`` idea with a bounded position budget and event-driven additions.
This module is deliberately independent of the V26 decision writer and MT5:
it neither reads nor changes ``decision.json``, prices, directions, stops, or
orders.  An integration owner may map approved allocations to broker volume.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


class PositionLifecycleState(str, Enum):
    """Lifecycle stages for one already-authorized directional idea."""

    IDLE = "IDLE"
    SCOUT_ACTIVE = "SCOUT_ACTIVE"
    CONFIRMATION_ELIGIBLE = "CONFIRMATION_ELIGIBLE"
    RUNNER_ELIGIBLE = "RUNNER_ELIGIBLE"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    REMAINING_BUDGET_CANCELLED = "REMAINING_BUDGET_CANCELLED"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class PositionBudget:
    """Fixed risk capacity and the uncommitted portion of that capacity."""

    total_budget: float
    allocated_budget: float
    remaining_budget: float
    initial_confidence: float
    current_confidence: float
    cancelled_budget: float = 0.0


@dataclass(frozen=True)
class PositionLifecycle:
    """State retained for one position construction lifecycle."""

    state: PositionLifecycleState = PositionLifecycleState.IDLE
    allocation_count: int = 0
    cancellation_reason: str = ""


@dataclass(frozen=True)
class ScalingDecision:
    """A non-executable allocation recommendation from a market event."""

    approved: bool
    allocation: float
    reason: str
    next_state: PositionLifecycleState


class PositionBudgetManager:
    """Creates, refreshes, allocates, and cancels bounded position budgets."""

    def create(self, total_budget: float, confidence: float) -> PositionBudget:
        total = self._non_negative(total_budget, "total_budget")
        return PositionBudget(total, 0.0, total, self._confidence(confidence), self._confidence(confidence))

    def refresh_confidence(self, budget: PositionBudget, confidence: float) -> PositionBudget:
        self._validate_budget(budget)
        return replace(budget, current_confidence=self._confidence(confidence))

    def allocate(self, budget: PositionBudget, requested_budget: float) -> PositionBudget:
        self._validate_budget(budget)
        requested = self._non_negative(requested_budget, "requested_budget")
        allocation = min(requested, budget.remaining_budget)
        return replace(
            budget,
            allocated_budget=round(budget.allocated_budget + allocation, 10),
            remaining_budget=round(budget.remaining_budget - allocation, 10),
        )

    def cancel_remaining(self, budget: PositionBudget) -> PositionBudget:
        self._validate_budget(budget)
        return replace(
            budget,
            cancelled_budget=round(budget.cancelled_budget + budget.remaining_budget, 10),
            remaining_budget=0.0,
        )

    @staticmethod
    def _confidence(value: float) -> float:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("confidence must be a number")
        return round(min(100.0, max(0.0, float(value))), 4)

    @staticmethod
    def _non_negative(value: float, name: str) -> float:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f"{name} must be a number")
        if value < 0:
            raise ValueError(f"{name} must be non-negative")
        return round(float(value), 10)

    @staticmethod
    def _validate_budget(budget: PositionBudget) -> None:
        if not isinstance(budget, PositionBudget):
            raise TypeError("budget must be a PositionBudget")
        if budget.allocated_budget + budget.remaining_budget + budget.cancelled_budget > budget.total_budget + 1e-8:
            raise ValueError("budget accounting exceeds total_budget")


class PositionLifecycleManager:
    """Applies only explicit lifecycle events; it contains no timer transitions."""

    def start_scout(self, lifecycle: PositionLifecycle) -> PositionLifecycle:
        self._require(lifecycle, PositionLifecycleState.IDLE)
        return replace(lifecycle, state=PositionLifecycleState.SCOUT_ACTIVE, allocation_count=1)

    def apply_scaling(self, lifecycle: PositionLifecycle, decision: ScalingDecision) -> PositionLifecycle:
        if not decision.approved:
            return lifecycle
        if lifecycle.state not in {PositionLifecycleState.SCOUT_ACTIVE, PositionLifecycleState.CONFIRMATION_ELIGIBLE}:
            raise ValueError("scaling is only valid from active scout or confirmation states")
        return replace(lifecycle, state=decision.next_state, allocation_count=lifecycle.allocation_count + 1)

    def cancel_remaining(self, lifecycle: PositionLifecycle, reason: str) -> PositionLifecycle:
        if lifecycle.state in {PositionLifecycleState.CLOSED, PositionLifecycleState.BUDGET_EXHAUSTED}:
            return lifecycle
        return replace(lifecycle, state=PositionLifecycleState.REMAINING_BUDGET_CANCELLED, cancellation_reason=reason)

    def close(self, lifecycle: PositionLifecycle) -> PositionLifecycle:
        return replace(lifecycle, state=PositionLifecycleState.CLOSED)

    @staticmethod
    def _require(lifecycle: PositionLifecycle, expected: PositionLifecycleState) -> None:
        if not isinstance(lifecycle, PositionLifecycle):
            raise TypeError("lifecycle must be a PositionLifecycle")
        if lifecycle.state != expected:
            raise ValueError(f"expected {expected.value}, got {lifecycle.state.value}")


class ScalingDecisionEngine:
    """Evaluates winner-only, confidence-refreshed, market-event scaling."""

    MIN_CONFIRMATION_CONFIDENCE = 60.0
    MIN_RUNNER_CONFIDENCE = 75.0

    def decide(
        self,
        budget: PositionBudget,
        lifecycle: PositionLifecycle,
        *,
        floating_pnl: float,
        confirmation_event: bool = False,
        continuation_event: bool = False,
        invalidation_event: bool = False,
    ) -> ScalingDecision:
        PositionBudgetManager._validate_budget(budget)
        if not isinstance(lifecycle, PositionLifecycle):
            raise TypeError("lifecycle must be a PositionLifecycle")
        if invalidation_event:
            return ScalingDecision(False, 0.0, "INVALIDATION_CANCELS_REMAINING_BUDGET", PositionLifecycleState.REMAINING_BUDGET_CANCELLED)
        if budget.remaining_budget <= 0:
            return ScalingDecision(False, 0.0, "POSITION_BUDGET_EXHAUSTED", PositionLifecycleState.BUDGET_EXHAUSTED)
        if floating_pnl <= 0:
            return ScalingDecision(False, 0.0, "WINNER_ONLY_SCALING", lifecycle.state)
        if lifecycle.state == PositionLifecycleState.SCOUT_ACTIVE and confirmation_event:
            if budget.current_confidence < self.MIN_CONFIRMATION_CONFIDENCE:
                return ScalingDecision(False, 0.0, "CONFIDENCE_REFRESH_BELOW_CONFIRMATION_THRESHOLD", lifecycle.state)
            return ScalingDecision(True, self._portion(budget, 0.50), "CONFIRMATION_EVENT", PositionLifecycleState.CONFIRMATION_ELIGIBLE)
        if lifecycle.state == PositionLifecycleState.CONFIRMATION_ELIGIBLE and continuation_event:
            if budget.current_confidence < self.MIN_RUNNER_CONFIDENCE:
                return ScalingDecision(False, 0.0, "CONFIDENCE_REFRESH_BELOW_RUNNER_THRESHOLD", lifecycle.state)
            return ScalingDecision(True, budget.remaining_budget, "CONTINUATION_EVENT", PositionLifecycleState.RUNNER_ELIGIBLE)
        return ScalingDecision(False, 0.0, "NO_QUALIFYING_MARKET_EVENT", lifecycle.state)

    @staticmethod
    def _portion(budget: PositionBudget, fraction: float) -> float:
        return round(min(budget.remaining_budget, budget.total_budget * fraction), 10)
