# RP AI Brain Phase 1 data contract

## Scope

This contract defines **internal, in-process** boundaries for the authoritative
V26 runtime only.  Phase 1 is a behavior-preserving extraction: it does not add
fields, remove fields, change values, or create a second publication format.
`decision.json` remains the V26 payload produced by the existing writer.

## Boundary rule

Every stage accepts a Python `dict` and returns the *same* `dict` object.  A
stage must not add a stage marker or mutate the payload merely to identify
itself.  Existing V26 functions remain the sole owners of all calculations.

| Stage | Input | Output | Phase 1 responsibility |
| --- | --- | --- | --- |
| Market Perception | Raw `market_state.json` dictionary | Unchanged market dictionary | Boundary around existing market observations. |
| Market Understanding | Perception dictionary | Unchanged market dictionary | Boundary before the existing V26 regime/classification logic. |
| Market Reasoning | V26 candidate decision dictionary | Unchanged candidate decision | Boundary around the existing thesis/entry pipeline. |
| Probability Engine | Candidate decision dictionary | Unchanged candidate decision | Boundary around existing confidence/probability-like telemetry only. |
| Expected Value Engine | Candidate decision dictionary | Unchanged candidate decision | Boundary around existing expectancy/RR processing only. |
| Position Intelligence | Candidate decision dictionary | Unchanged candidate decision | Boundary around existing risk, sizing, legs, and management processing only. |
| Decision Publication | Final V26 payload dictionary | Unchanged final payload dictionary | Boundary immediately before the existing atomic writer. |

## Compatibility invariants

The following must remain identical for a given deterministic V26 input:

* BUY/SELL/WAIT decision state and all existing action aliases.
* Entry, SL, TP, confidence, probability-like telemetry, and every existing
  payload field.
* The serialized `decision.json` schema and existing atomic publication path.

Stage boundaries are deliberately metadata-free so they cannot alter the
published payload or MT5/dashboard contracts.
