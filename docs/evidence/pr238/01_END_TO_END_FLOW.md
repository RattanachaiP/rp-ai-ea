# PR238 Blocked End-to-End Verification Report

**Collection date:** 2026-07-28 UTC  
**Baseline:** `a513469`  
**Verdict:** **INCOMPLETE — live MT5 Demo prerequisites are unavailable on this host.**

No production artifact or broker identifier was synthesized. Repository checks establish the implemented boundaries, but cannot establish that a live flow occurred.

| Boundary | Existence in this run | Contract / producer / version | UUID and sequence | Freshness | Publication semantics | Result |
|---|---:|---|---|---|---|---|
| Writer → `market_state.json` | Not observed | Writer declares the governed market-state fields | Reader validates source UUID and monotonic sequence | Reader enforces 30 seconds | Writer uses temporary publication and move | NOT EXECUTED |
| `market_state.json` → Runtime | Not observed | `GovernedMarketStateReader` validates producer `RP_AI_MT5_MARKET_STATE`, `V1`, schema `1.0` | Source UUID, generated snapshot UUID, duplicate and rollback checks | Enforced | Stable-inode read verifies replacement | NOT EXECUTED |
| Runtime → `decision.json` | Not observed | Runtime publication contract is checked by package assembly | Decision UUID, market sequence, and source UUID checked | Enforced | Same-directory best-effort replacement is implemented | NOT EXECUTED |
| `decision.json` → `execution_package.json` | Not observed | Exact package contract and runtime producer/version checked | Decision UUID, source UUID, and strictly increasing sequence checked | Enforced | Same-directory `os.replace` plus fsync; platform guarantee not claimed | NOT EXECUTED |
| Package → MT5 Executor | Not observed | Exact generated MQL contract, producer and versions checked | Execution/decision/source UUID and monotonic sequence checked | Enforced | Consumer reads completed package | NOT EXECUTED |
| Executor → Broker | No connected terminal | Symbol, trade mode, connection, tick, volume, margin, and stops are checked | Execution UUID is journaled before `OrderSend` | Tick age enforced | Crash journal/state persisted before submission | NOT EXECUTED |
| Broker → `execution_result.json` | Not observed | Result contains execution UUID, ticket, retcode, broker time and status | Execution UUID is copied from package | Broker time recorded | Same-directory temporary-file, fail-closed, best-effort replacement | NOT EXECUTED |

## Integration defect corrected

The executor previously truncated `executor_state.json` and `execution_result.json` in place. A crash could expose partial JSON at the final hand-off. Both authoritative documents now use a publication-specific, collision-resistant temporary name in the same directory, flush/close, stale-file rejection and governed cleanup, and best-effort `FileMove(..., FILE_REWRITE)` replacement. Replacement failure preserves the prior destination by never deliberately deleting it and fails the publication closed; no cross-platform crash-atomic guarantee is claimed. No strategy, governance, or component ownership changed.

## Exact live boundary

The first unfulfilled boundary is **MT5 Writer → `market_state.json`**. The collection host has no published canonical market state and therefore the downstream runtime must remain fail-closed. A real Demo execution cannot be truthfully certified here.

If result publication fails after a broker response exists, the executor records an authoritative `UNKNOWN_OUTCOME` journal/state transition carrying the execution UUID plus broker retcode and ticket in the reason. The trace remains observational only.
