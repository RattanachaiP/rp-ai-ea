# RP AI Brain Phase 2A data contract

## Scope

This contract defines **internal, in-process** boundaries for the authoritative
V26 runtime only. Phase 2A replaces the Market Perception identity wrapper with
an observation-only object while preserving the Phase 1 publication guarantees.
`decision.json` remains the V26 payload produced by the existing writer.

## Boundary rule

Market Perception accepts a Python `dict` and returns a private
`MarketPerception` object. Market Understanding consumes it and returns a
private `MarketUnderstanding` object. Market Reasoning consumes that object and
returns a private immutable `MarketReasoning` explanation, which retains the
understanding and therefore the original dictionary by object identity for the
unchanged V26 path. All later stages accept and return the same candidate
decision dictionary.
No stage may add a marker or mutate the payload merely to identify itself.
Existing V26 functions remain the sole owners of all calculations.

| Stage | Input | Output | Phase 1 responsibility |
| --- | --- | --- | --- |
| Market Perception | Raw `market_state.json` dictionary | `MarketPerception` object | Extracts observations only: trend, swing high/low, structure, liquidity sweep, volatility, ATR availability, VWAP relation, session, momentum, compression/expansion, and impulse. It carries the original market dictionary privately for the next boundary. It does not decide, score, or determine direction. |
| Market Understanding | `MarketPerception` | `MarketUnderstanding` object | Interprets observations as regime, trend/structure, expansion/compression, pullback/transition, liquidity, momentum, volatility, narrative, invalid conditions, and context quality. It does not decide, score, or determine direction. The runtime unwraps the original market dictionary by identity before existing V26 regime/classification logic. |
| Market Reasoning | `MarketUnderstanding` | `MarketReasoning` object | Explains the current state plus contextual continuation, reversal, and wait cases; records supporting, conflicting, and uncertain evidence; and creates a human-readable narrative. It does not decide, score, calculate confidence/probability/expectancy, construct risk, or determine direction. The runtime unwraps the original market dictionary by identity before existing V26 regime/classification logic. |
| Probability Engine | `MarketUnderstanding` + `MarketReasoning` | immutable private `ProbabilityAssessment` | Estimates only continuation, reversal, range, breakout, and no-trade market-state probabilities. Every estimate records supporting/conflicting evidence and uncertainty. It never estimates BUY/SELL, changes V26 confidence/scores, or enters the decision payload. |
| Expected Value Engine | Candidate decision dictionary | Unchanged candidate decision | Boundary around existing expectancy/RR processing only. |
| Position Intelligence | Candidate decision dictionary | Unchanged candidate decision | Boundary around existing risk, sizing, legs, and management processing only. |
| Decision Publication | Final V26 payload dictionary | Unchanged final payload dictionary | Boundary immediately before the existing atomic writer. |

## Compatibility invariants

The following must remain identical for a given deterministic V26 input:

* BUY/SELL/WAIT decision state and all existing action aliases.
* Entry, SL, TP, confidence, probability-like telemetry, and every existing
  payload field.
* The serialized `decision.json` schema and existing atomic publication path.

The perception object is deliberately not serialized, merged into a candidate
decision, or passed to the writer. Market Understanding immediately unwraps its
original market dictionary into the unchanged V26 path. All other stage
boundaries are metadata-free so they cannot alter the published payload or
MT5/dashboard contracts.
