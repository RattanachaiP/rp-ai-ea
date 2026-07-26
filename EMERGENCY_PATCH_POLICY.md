# EMERGENCY_PATCH_POLICY — V27

Emergency patches may alter post-entry trade management only when the change is implemented through the Trade Management Dashboard runtime configuration layer or through the Exit Authority Manager contract.

Emergency patches must not redesign AI direction, bias, entry timing, signal generation, or market classification. If an emergency requires an architectural exception, update the four authority documents before modifying runtime code.

All emergency exit behavior must preserve one effective exit owner and must publish dashboard profile metadata in `decision.json` for auditability.

## V28 rebuild boundary

The V28 thinking-model rebuild is not an emergency patch. Emergency-patch
authority cannot be used to implement, tune, or bypass the pending V28 decision
philosophy. Until explicit approval of `docs/v28/V28_DECISION_PHILOSOPHY.md`
and `docs/v28/V28_EXPECTANCY_FIRST_ARCHITECTURE_ADDENDUM.md`, no V28 runtime
changes are authorized and no V27 filters, cooldowns, waits, score adjustments,
patch stacks, or runtime layers may be introduced.

## PR186 boundary

PR186 Execution Readiness is governance-only and advisory-only. Emergency-patch authority may not use a readiness state to alter strategy, bias, direction, risk, decision publication, runtime activation, broker communication, position management, exits, or execution.

## PR187 boundary

PR187 Execution Environment Intelligence is governance-only and advisory-only.
Emergency-patch authority may not use an environment state or quality profile to
alter strategy, bias, direction, risk, decision publication, runtime activation,
broker communication, position management, exits, or execution.

## PR188 boundary

PR188 Execution Feasibility is governance-only and advisory-only. Emergency-patch authority may not use a feasibility state to alter strategy, bias, direction, risk, decision publication, runtime activation, broker communication, position management, exits, or execution.

## PR189 boundary

PR189 Execution Package Assembly is governance-only and advisory-only.
Emergency-patch authority may not use a package or package state to alter
strategy, bias, direction, risk, decision publication, runtime activation,
broker communication, position management, exits, or execution.

## PR190 boundary

PR190 is an immutable, fail-closed Execution Package consumer interface, not a
validation gateway or authority stage. Emergency-patch authority may not add
recovery, repair, evaluation, recommendation, publication, broker, position,
exit, or execution behavior to package loading.

## PR192 boundary

PR192 is the permanent immutable Runtime-to-Executor public interface.
Emergency-patch authority may not bypass its canonical codec, weaken its
compatibility or integrity checks, add fallback or repair, expose governance
artifacts to the Executor, or add trading and position-management behavior to
the contract.

## PR194 boundary

PR194 is the fail-closed Executor consumer of `execution_context.json` only.
Emergency-patch authority may not weaken its canonical, integrity, identity,
compatibility, timestamp, advisory-marker, or exact-schema checks; add fallback,
repair, or partial loading; or connect it to governance, package, confidence,
strategy, or Runtime implementation artifacts.
