# RP AI Brain V1 Public Interface Freeze

**Architecture version:** `V1 Frozen`
**Status:** Frozen on 2026-07-20
**Authority:** `brain/DATA_CONTRACT.md`

## Change-control rule

The interfaces below are frozen. Future development must preserve them unless
an explicit governance approval changes the architecture. That approval must
identify the new contract version, affected interfaces, compatibility and
rollback plan, and validation evidence. This freeze adds no analytical module,
runtime feature, strategy migration, or decision migration.

## Typed Brain interfaces

| Layer | Public callable | Defined input | Defined output | Guarantees / prohibitions |
| --- | --- | --- | --- | --- |
| Perception | `extract_market_perception(market_state: Mapping[str, Any]) -> MarketPerception` | Caller-owned raw market-state mapping. | Frozen `MarketPerception`. | Observation only. Never selects a trade, score, direction, or payload field; never mutates input. |
| Understanding | `interpret_market_understanding(perception: MarketPerception) -> MarketUnderstanding` | A `MarketPerception`; any other type raises `TypeError`. | Frozen `MarketUnderstanding`. | Descriptive context only. May read Perception; has no probability, decision, score, confidence, risk, execution, or publication dependency. |
| Reasoning | `reason_about_market(understanding: MarketUnderstanding) -> MarketReasoning` | A `MarketUnderstanding`; any other type raises `TypeError`. | Frozen `MarketReasoning`. | Explanation/evidence only. May read Understanding; does not mutate it or produce a decision/probability/risk instruction. |
| Probability | `estimate_market_probabilities(understanding: MarketUnderstanding, reasoning: MarketReasoning) -> ProbabilityAssessment` | Matching Understanding and Reasoning; mismatched identity raises `ValueError`, wrong types raise `TypeError`. | Frozen `ProbabilityAssessment` containing frozen `MarketStateProbability` entries. | Non-directional market-state telemetry only: continuation, reversal, range, breakout, no-trade. Never BUY/SELL, confidence, score, risk, decision, or payload output. |

## Frozen record types

All Brain dataclasses are declared with `@dataclass(frozen=True)`:

* `MarketPerception`
* `MarketUnderstanding`
* `MarketReasoning`
* `MarketStateProbability`
* `ProbabilityAssessment`

Frozen means their attributes cannot be reassigned after construction.
`MarketPerception.market_state` is intentionally the caller-owned raw mapping
preserved by identity for the unchanged V26 path; the Brain does not mutate it.
It is not a Brain-owned mutable data store.

## Compatibility boundaries retained outside the typed pipeline

The authoritative V26 engine exposes the following frozen compatibility
boundaries. Each has the exact identity contract
`dict[str, Any] -> same dict[str, Any]` and does not add stage metadata:

* `brain_probability_engine(candidate_decision)`
* `brain_expected_value_engine(candidate_decision)`
* `brain_position_intelligence(candidate_decision)`
* `brain_decision_publication(final_payload)`

`brain_market_perception`, `brain_market_understanding`,
`brain_market_reasoning`, and `brain_probability_assessment` are V26 adapter
wrappers for the typed interfaces above. They do not publish objects or
probability telemetry into `decision.json`.

## Explicitly not public V1 capabilities

The V1 Brain has no public decision, signal, strategy, expected-value,
position-management, execution, writer, MT5, dashboard, or learning interface.
The V26 decision engine and its `decision.json` writer remain authoritative.
