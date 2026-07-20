# RP AI Brain V1 Frozen data contract

> **Status: V1 FROZEN — 2026-07-20.** This is the authoritative public
> contract for the implemented Brain pipeline.  It supersedes the Phase 2A
> wording below without changing runtime behaviour.  A change to a named type,
> function signature, stage order, ownership rule, or published-payload rule
> requires explicit governance approval before implementation.

## Scope

This contract defines **internal, in-process** boundaries for the authoritative
V26 runtime only. The V1 Brain remains observational and preserves the Phase 1
publication guarantees.
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

| Stage | Input | Output | Frozen responsibility |
| --- | --- | --- | --- |
| Market Perception | Raw `market_state.json` dictionary | `MarketPerception` object | Extracts observations only: trend, swing high/low, structure, liquidity sweep, volatility, ATR availability, VWAP relation, session, momentum, compression/expansion, and impulse. It carries the original market dictionary privately for the next boundary. It does not decide, score, or determine direction. |
| Market Understanding | `MarketPerception` | `MarketUnderstanding` object | Interprets observations as regime, trend/structure, expansion/compression, pullback/transition, liquidity, momentum, volatility, narrative, invalid conditions, and context quality. It does not decide, score, or determine direction. The runtime unwraps the original market dictionary by identity before existing V26 regime/classification logic. |
| Market Reasoning | `MarketUnderstanding` | `MarketReasoning` object | Explains the current state plus contextual continuation, reversal, and wait cases; records supporting, conflicting, and uncertain evidence; and creates a human-readable narrative. It does not decide, score, calculate confidence/probability/expectancy, construct risk, or determine direction. The runtime unwraps the original market dictionary by identity before existing V26 regime/classification logic. |
| Probability Engine | `MarketUnderstanding` + `MarketReasoning` | immutable private `ProbabilityAssessment` | Estimates only continuation, reversal, range, breakout, and no-trade market-state probabilities. Every estimate records supporting/conflicting evidence and uncertainty. It never estimates BUY/SELL, changes V26 confidence/scores, or enters the decision payload. |
| Expected Value Engine | Candidate decision dictionary | Unchanged candidate decision | Boundary around existing expectancy/RR processing only. |
| Position Intelligence | Candidate decision dictionary | Unchanged candidate decision | Boundary around existing risk, sizing, legs, and management processing only. |
| Decision Publication | Final V26 payload dictionary | Unchanged final payload dictionary | Boundary immediately before the existing atomic writer. |

## V1 interface and ownership rules

The four typed Brain layers have one permitted dependency direction:

`raw market-state Mapping -> MarketPerception -> MarketUnderstanding -> MarketReasoning -> ProbabilityAssessment`

* Each typed output is a `@dataclass(frozen=True)`. Its fields cannot be
  reassigned after construction. Evidence collections are tuples.
* `MarketPerception.market_state` deliberately preserves the caller-owned raw
  mapping by object identity so the unchanged V26 runtime can consume that
  exact mapping. Brain layers never mutate it; ownership remains with the V26
  market reader/runtime.
* Understanding may read Perception only; Reasoning may read Understanding
  only; Probability may read Understanding and its matching Reasoning only.
  Probability validates that `reasoning.understanding is understanding`.
* No typed Brain layer imports the V26 engine, MT5, dashboard, writer,
  executor, decision payload, confidence, score, risk, or trade-management
  code. Probability is telemetry only and has no reverse dependency into an
  earlier layer.
* The legacy `brain_probability_engine`, `brain_expected_value_engine`,
  `brain_position_intelligence`, and `brain_decision_publication` functions
  are compatibility identities around the pre-existing V26 decision path. They
  are not analytical Brain layers and must return their input dictionary
  unchanged by object identity.

## Freeze and change control

**Brain Version: V1 Frozen.** Future development must preserve every interface
and invariant in this document and `analysis/BRAIN_PUBLIC_INTERFACE.md`.
Changes are prohibited unless a governance approval explicitly names the
contract version, affected interfaces, compatibility/rollback plan, and
validation evidence. In particular, V1 does not authorize a new analytical
module, runtime feature, strategy migration, decision migration, payload field,
or probability-to-decision connection.

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
