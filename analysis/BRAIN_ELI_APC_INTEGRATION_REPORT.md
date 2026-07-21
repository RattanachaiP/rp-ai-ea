# BRAIN ELI–APC Controlled Integration Report

## Purpose and boundary
This change introduces `EntryConstructionCoordinator`, a pure, deterministic domain boundary between Entry Location Intelligence (ELI) and Adaptive Position Construction (APC). It consumes ELI's already-calculated `EntryLocationAssessment`; it does not recalculate swing position, ATR extension, pullback, risk/reward, or location score.

ELI owns location eligibility. APC owns bounded initial and winner-only scale allocation. The coordinator only grants or denies APC's evaluation permission and returns an explainable, non-executable decision. It has no runtime, Writer, Executor, `decision.json`, MT5, broker, stop/target, close, or reversal coupling.

## Contracts
Input: ELI assessment (including assessed direction), APC request/direction and event evidence, lifecycle, and budget. Output: `EntryConstructionDecision` provides permission, action, ELI state/score, lifecycle state, total/used/remaining budget, preservation flag, allocation recommendation, reasons, and deterministic trace.

| ELI state | No active position | Existing position |
| --- | --- | --- |
| `ENTRY_ALLOWED` | APC may evaluate `ALLOW_START` | APC may evaluate `ALLOW_SCALE` using its own winner-only rules |
| `WAIT_PULLBACK`, `WAIT_CONFIRMATION` | `WAIT_LOCATION`, allocation 0 | `HOLD_EXISTING`, allocation 0 |
| `BLOCK_*` | `BLOCK_LOCATION`, allocation 0 | `HOLD_EXISTING`, allocation 0 |

WAIT is recoverable on new evidence/assessment and never consumes budget. BLOCK is a hard denial for the current attempt. Neither action closes or modifies existing exposure. A permitted ELI assessment cannot bypass APC confidence, event, or winner-only controls.

## Safety and trace
Direction must match exactly. Missing or unknown assessments/states, invalid score/reasons, invalid accounting (including negative remaining budget), and contradictory lifecycle are fail-safe `BLOCK_LOCATION` decisions. Every result contains ordered, deterministic trace entries for ELI state, action, and allocation plus retained reasons.

## Tests and limitations
Integration tests cover all ELI WAIT/BLOCK categories, initial/start and scale gating, confidence non-override, budget preservation, existing-position safety, APC-only scale rules, malformed/fail-safe inputs, determinism, and no timer input. Existing APC and ELI tests remain regression coverage.

This is deliberately domain-only. A future separately approved Decision Pipeline integration may create an assessment from the same market event and invoke this coordinator before construction; it must preserve the ownership rule above and must not introduce a timer, broker coupling, or direct ELI allocation.
