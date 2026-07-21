"""Pure, event-driven ELI-to-APC construction permission boundary.

This domain coordinator consumes ELI's authoritative assessment without
recalculating location geometry.  It neither publishes decisions nor touches
broker positions; callers apply an approved allocation separately.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from brain.adaptive_position_construction import (
    PositionBudget, PositionLifecycle,
    PositionLifecycleState, ScalingDecisionEngine,
)
from brain.entry_location_intelligence import EntryLocationAssessment, EntryState


class ConstructionAction(str, Enum):
    ALLOW_START = "ALLOW_START"
    ALLOW_SCALE = "ALLOW_SCALE"
    WAIT_LOCATION = "WAIT_LOCATION"
    BLOCK_LOCATION = "BLOCK_LOCATION"
    HOLD_EXISTING = "HOLD_EXISTING"
    NO_ACTION = "NO_ACTION"


@dataclass(frozen=True)
class EntryConstructionRequest:
    direction: str
    initial_allocation: float = 0.0
    floating_pnl: float = 0.0
    confirmation_event: bool = False
    continuation_event: bool = False
    invalidation_event: bool = False


@dataclass(frozen=True)
class EntryConstructionDecision:
    construction_permission: bool
    construction_action: ConstructionAction
    eli_entry_state: str
    location_score: float | None
    position_state: PositionLifecycleState
    budget_total: float
    budget_used: float
    budget_remaining: float
    budget_preserved: bool
    decision_reasons: tuple[str, ...]
    decision_trace: tuple[str, ...]
    allocation: float = 0.0


class EntryConstructionCoordinator:
    """Hard permission gate around APC start and winner-only scaling rules."""

    def __init__(self, scaling_engine: ScalingDecisionEngine | None = None) -> None:
        self.scaling_engine = scaling_engine or ScalingDecisionEngine()

    def decide(self, assessment: EntryLocationAssessment | None, request: EntryConstructionRequest,
               lifecycle: PositionLifecycle, budget: PositionBudget) -> EntryConstructionDecision:
        invalid = self._invalid_context(assessment, request, lifecycle, budget)
        if invalid:
            return self._deny("BLOCK_LOCATION", invalid, assessment, lifecycle, budget)

        assert assessment is not None
        existing = lifecycle.state is not PositionLifecycleState.IDLE
        if assessment.entry_state in {EntryState.WAIT_PULLBACK, EntryState.WAIT_CONFIRMATION}:
            return self._deny("HOLD_EXISTING" if existing else "WAIT_LOCATION", assessment.reasons, assessment, lifecycle, budget)
        if assessment.entry_state is not EntryState.ENTRY_ALLOWED or not assessment.entry_permission:
            return self._deny("HOLD_EXISTING" if existing else "BLOCK_LOCATION", assessment.reasons, assessment, lifecycle, budget)

        if lifecycle.state is PositionLifecycleState.IDLE:
            if not self._valid_non_negative(request.initial_allocation) or request.initial_allocation <= 0:
                return self._deny("NO_ACTION", ("INVALID_INITIAL_ALLOCATION",), assessment, lifecycle, budget)
            allocation = min(request.initial_allocation, budget.remaining_budget)
            if allocation <= 0:
                return self._deny("NO_ACTION", ("POSITION_BUDGET_EXHAUSTED",), assessment, lifecycle, budget)
            return self._allow(ConstructionAction.ALLOW_START, allocation, ("ELI_ENTRY_ALLOWED", "APC_START_EVALUATION_ALLOWED"), assessment, lifecycle, budget)

        scale = self.scaling_engine.decide(budget, lifecycle, floating_pnl=request.floating_pnl,
                                           confirmation_event=request.confirmation_event,
                                           continuation_event=request.continuation_event,
                                           invalidation_event=request.invalidation_event)
        if not scale.approved:
            return self._deny("HOLD_EXISTING", ("ELI_ENTRY_ALLOWED", scale.reason), assessment, lifecycle, budget)
        return self._allow(ConstructionAction.ALLOW_SCALE, scale.allocation, ("ELI_ENTRY_ALLOWED", scale.reason), assessment, lifecycle, budget)

    def _invalid_context(self, assessment, request, lifecycle, budget) -> tuple[str, ...]:
        if not isinstance(assessment, EntryLocationAssessment): return ("MISSING_OR_INVALID_ELI_ASSESSMENT",)
        if not isinstance(request, EntryConstructionRequest) or request.direction not in {"BUY", "SELL"}: return ("INVALID_APC_REQUEST_DIRECTION",)
        if assessment.direction != request.direction: return ("ELI_APC_DIRECTION_MISMATCH",)
        if not isinstance(assessment.entry_state, EntryState): return ("UNKNOWN_ELI_STATE",)
        if not self._valid_non_negative(assessment.location_score) or assessment.location_score > 100: return ("INVALID_LOCATION_SCORE",)
        if not isinstance(assessment.reasons, tuple) or not assessment.reasons or not all(isinstance(reason, str) and reason for reason in assessment.reasons): return ("MALFORMED_ELI_REASONS",)
        if not isinstance(lifecycle, PositionLifecycle) or not isinstance(budget, PositionBudget): return ("INVALID_APC_STATE",)
        if not all(self._valid_non_negative(value) for value in (budget.total_budget, budget.allocated_budget, budget.remaining_budget, budget.cancelled_budget)): return ("INVALID_APC_BUDGET",)
        if abs(budget.allocated_budget + budget.remaining_budget + budget.cancelled_budget - budget.total_budget) > 1e-8: return ("INVALID_APC_BUDGET",)
        if lifecycle.state is PositionLifecycleState.IDLE and lifecycle.allocation_count != 0: return ("CONTRADICTORY_APC_LIFECYCLE",)
        if lifecycle.state is not PositionLifecycleState.IDLE and lifecycle.allocation_count <= 0: return ("CONTRADICTORY_APC_LIFECYCLE",)
        return ()

    @staticmethod
    def _valid_non_negative(value: object) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0

    def _deny(self, action: str, reasons: tuple[str, ...], assessment, lifecycle, budget) -> EntryConstructionDecision:
        return self._result(False, ConstructionAction(action), 0.0, reasons, assessment, lifecycle, budget)

    def _allow(self, action, allocation, reasons, assessment, lifecycle, budget) -> EntryConstructionDecision:
        return self._result(True, action, allocation, reasons, assessment, lifecycle, budget)

    @staticmethod
    def _result(permission, action, allocation, reasons, assessment, lifecycle, budget) -> EntryConstructionDecision:
        state = assessment.entry_state.value if isinstance(assessment, EntryLocationAssessment) and isinstance(assessment.entry_state, EntryState) else "UNKNOWN"
        score = assessment.location_score if isinstance(assessment, EntryLocationAssessment) else None
        return EntryConstructionDecision(permission, action, state, score, lifecycle.state if isinstance(lifecycle, PositionLifecycle) else PositionLifecycleState.IDLE, budget.total_budget if isinstance(budget, PositionBudget) else 0.0, budget.allocated_budget if isinstance(budget, PositionBudget) else 0.0, budget.remaining_budget if isinstance(budget, PositionBudget) else 0.0, True, tuple(reasons), (f"ELI_STATE={state}", f"ACTION={action.value}", f"ALLOCATION={allocation:.10f}"), allocation)
