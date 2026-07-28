# PR238 End-to-End Flow Verification

**Collection date:** 2026-07-28 UTC  
**Baseline:** `a513469`  
**Verdict:** **INCOMPLETE — live MT5 Demo prerequisites are unavailable on this host.**

No production artifact or broker identifier was synthesized. Repository checks establish the implemented boundaries, but cannot establish that a live flow occurred.

| Boundary | Existence in this run | Contract / producer / version | UUID and sequence | Freshness | Atomic replacement | Result |
|---|---:|---|---|---|---|---|
| Writer → `market_state.json` | Not observed | Writer declares the governed market-state fields | Reader validates source UUID and monotonic sequence | Reader enforces 30 seconds | Writer uses temporary publication and move | NOT EXECUTED |
| `market_state.json` → Runtime | Not observed | `GovernedMarketStateReader` validates producer `RP_AI_MT5_MARKET_STATE`, `V1`, schema `1.0` | Source UUID, generated snapshot UUID, duplicate and rollback checks | Enforced | Stable-inode read verifies replacement | NOT EXECUTED |
| Runtime → `decision.json` | Not observed | Runtime publication contract is checked by package assembly | Decision UUID, market sequence, and source UUID checked | Enforced | Atomic write is implemented | NOT EXECUTED |
| `decision.json` → `execution_package.json` | Not observed | Exact package contract and runtime producer/version checked | Decision UUID, source UUID, and strictly increasing sequence checked | Enforced | `os.replace` plus fsync | NOT EXECUTED |
| Package → MT5 Executor | Not observed | Exact generated MQL contract, producer and versions checked | Execution/decision/source UUID and monotonic sequence checked | Enforced | Consumer reads completed package | NOT EXECUTED |
| Executor → Broker | No connected terminal | Symbol, trade mode, connection, tick, volume, margin, and stops are checked | Execution UUID is journaled before `OrderSend` | Tick age enforced | Crash journal/state persisted before submission | NOT EXECUTED |
| Broker → `execution_result.json` | Not observed | Result contains execution UUID, ticket, retcode, broker time and status | Execution UUID is copied from package | Broker time recorded | Corrected in PR238 to temporary-file replacement | NOT EXECUTED |

## Integration defect corrected

The executor previously truncated `executor_state.json` and `execution_result.json` in place. A crash could expose partial JSON at the final hand-off. Both authoritative documents now use a same-directory temporary file, flush/close, and `FileMove(..., FILE_REWRITE)` replacement. No strategy, governance, or component ownership changed.

## Exact live boundary

The first unfulfilled boundary is **MT5 Writer → `market_state.json`**. The collection host has no published canonical market state and therefore the downstream runtime must remain fail-closed. A real Demo execution cannot be truthfully certified here.
