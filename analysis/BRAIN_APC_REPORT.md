# Adaptive Position Construction (APC) — Phase 1 Report

## Scope

Phase 1 adds a standalone, in-memory APC domain model. It is deliberately not
wired to the V26 decision engine, MT5 executor, dashboard, or `decision.json`.
This preserves all existing strategy, entry, direction, timing, payload, and
exit-authority behavior while providing a testable construction contract for a
future approved integration.

## Delivered components

- `PositionBudgetManager` replaces a fixed target-lot abstraction with a
  `PositionBudget`: total, allocated, remaining, and cancelled budget plus
  initial/current confidence.
- `PositionLifecycleManager` governs `IDLE`, scout, confirmation, runner,
  budget-exhausted, remaining-budget-cancelled, and closed states.
- `ScalingDecisionEngine` permits additions only when a position is profitable,
  current confidence meets its threshold, and an explicit confirmation or
  continuation market event is supplied.
- Dynamic confidence refresh is explicit through `refresh_confidence`.
- An invalidation event yields a remaining-budget cancellation decision; the
  budget and lifecycle managers apply the cancellation without affecting any
  already allocated position.

## Safety and compatibility

- Scaling is winner-only; no averaging losers, martingale, hedging, or
  time-based scaling exists in APC.
- No `decision.json` field or schema was added, removed, or modified.
- APC contains no price, lot, direction, order, stop, target, broker, or timer
  input. Allocation units are abstract budget units to be mapped by a future
  authorized execution owner.

## Validation

The APC tests cover event-driven winner-only scaling, remaining-budget
accounting, confidence refresh rejection, invalidation cancellation, and the
absence of time-based inputs/transitions.
