# Runtime Writer Adapter — V27.4 Report

## Purpose and architecture boundary

`runtime/writer_adapter.py` is the sole translation boundary from the immutable
Brain `DecisionPackage` to a runtime-ready `RuntimeDecisionPayload`. It is
outside the pure `brain/` package because it owns a runtime contract, while the
Brain remains unaware of runtime publication. The adapter validates and
normalizes only; it performs no analysis and does not alter trading intent.

**Architecture rule proposed for authority:** The Writer Adapter is the sole
translation boundary between Brain `DecisionPackage` objects and runtime
publication payloads. It may validate and normalize contracts but must not
perform analysis, alter trading intent, publish files, invoke MT5, or execute
orders. Invalid or contradictory packages must become non-executable fail-safe
WAIT payloads.

Architecture authority documents are unchanged because this implementation
does not amend their approved policy.

## Input and output contracts

Input is exactly `brain.decision_pipeline.DecisionPackage`: direction,
confidence, probability, expected value, ELI location fields, coordinator
action, APC total/used/remaining budget, final decision, and ordered trace.
The adapter does not call the decision pipeline or any upstream Brain module.

Output is frozen `RuntimeDecisionPayload`, with JSON-compatible primitive
fields and tuples of strings:

- `schema_version`, normalized `decision`, `direction`, `entry_permission`,
  `entry_state`, `construction_action`, and derived `executable`;
- `confidence`, `probability`, `expected_value`, `location_score`, and the
  three position-budget fields;
- `decision_reasons`, `decision_trace`, and `fail_safe`.

The adapter accepts Brain's existing `TRADE` decision for compatibility and
normalizes it to the evaluated `BUY` or `SELL` direction. Direct `BUY` and
`SELL`, `WAIT`, `BLOCK`, `HOLD_EXISTING`, and `NO_ACTION` contracts are also
explicitly supported. No broker values are created.

## Permission, executability, and budget validation

Permission is preserved only; it is never created. A directional executable
payload requires a `BUY`/`SELL` runtime decision, true permission,
`ENTRY_ALLOWED`, and `ALLOW_START` or `ALLOW_SCALE`. WAIT, BLOCK,
HOLD_EXISTING, and NO_ACTION are always non-executable. WAIT/BLOCK states may
not use an allow action; a WAIT decision may not have permission; and all
directional decisions require a permitted `ENTRY_ALLOWED` contract.

Every numeric field is finite. Confidence and location score are bounded to
0–100; probability is bounded to 0–1. Budget total, used, and remaining must
be non-negative, each component may not exceed total, and used plus remaining
must equal total within `1e-8`. The adapter never increases exposure to repair
an invalid budget.

## Fail-safe, trace, and serialization behavior

Missing packages, unknown enums, invalid types or numbers (including NaN and
Infinity), malformed traces, contradictory fields, invalid budgets, and any
unexpected exception return a complete safe payload: `WAIT`, `NONE`, false
permission, `FAIL_SAFE`, `NO_ACTION`, zeroed numeric values, and
`executable=false`. Deterministic fail-safe reasons are retained in both
reasons and trace.

For valid input, source trace ordering is retained exactly and the deterministic
`WriterAdapter=VALID` boundary item is appended. Values are limited to strings,
booleans, finite floats, and tuples of strings; no JSON serialization is
performed here.

## Backward compatibility and non-responsibilities

The existing legacy writer uses `TRADE`/`NO_TRADE` and a separate, file-writing
contract. This PR does not modify it, its schema, Writer behavior, or any
Executor behavior. `TRADE` normalization is conservative compatibility for the
new runtime DTO only. The legacy writer's lack of the new fields remains a
known transitional contract difference for the future publication phase.

The adapter has no filesystem, JSON, Writer, Executor, MT5, broker, order, or
runtime-loop dependency. It does not publish `decision.json`, atomically write
files, calculate probability/EV/location, re-run ELI/APC, change allocation,
or make market decisions.

## Test coverage, limitations, and next phase

`tests/test_writer_adapter.py` covers valid BUY/SELL, all non-executable final
decisions, contradictory permission/action/state combinations, unknown values,
invalid and non-finite numerics, budget accounting, malformed traces,
determinism, immutability, and static import safety. Existing pipeline and
ELI/APC tests remain regression coverage.

This DTO is intentionally unpublished and has no sequence/freshness metadata
because those are publication-owner responsibilities. The next phase is a
separate Decision Publication component owning JSON serialization, atomic
replacement, `decision.json`, and freshness/sequence publication.
