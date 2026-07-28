# PR266 V28 Operational Qualification

## Authority and boundaries

PR266 is a read-only qualification layer above the immutable PR260–PR265 governed
pipeline. It neither changes pipeline decisions nor publishes, delivers, submits, or
recovers an order. V27 remains the only production execution authority. A successful
result is **READY FOR HUMAN REVIEW**, never production authorization.

## Qualification architecture

1. `qualification_campaign` binds ordered observations to an expiring campaign and
   explicit prior-campaign lineage.
2. `runtime_stability_monitor` checks heartbeat and sequence continuity, stable
   action-cohort replay identities, health, and certification integrity.
3. `shadow_campaign_runner` requires repeated BUY, SELL, and HOLD evidence and compares
   replay, execution, and certification equality.
4. `delivery_reliability_validator` counts publication, validation, delivery, replay,
   and certification outcomes. Any failure or recovery attempt fails qualification.
5. `campaign_statistics` aggregates immutable history without adding readiness policy.
6. `qualification_registry` preserves explicit append-only, identity-linked history.
7. `qualification_report` binds all reports and emits the sole operational
   recommendation.

## Campaign schema

A campaign contains a SHA-256 identity over policy, lineage identity, UTC start and
expiry, ordered immutable runs, and the permanently false `production_authorized`
field. Every run binds ordinal, action, observation time, complete PR265 certification,
runtime-health identity, publication/validation/delivery outcomes, recovery evidence,
and its own deterministic identity. Runs must be contiguous, chronological, within the
campaign window, and use only BUY, SELL, or HOLD.

## Fail-closed assessment

Replay or certification drift, unhealthy or corrupt runtime state, heartbeat or
sequence discontinuity, incomplete repeated action coverage, delivery failure,
forbidden recovery, cross-report campaign mismatch, or an incomplete campaign produces
FAIL. Expiry is evaluated against an explicit caller-supplied UTC time, so replay never
depends on a wall clock. Qualification reports are canonical JSON and deterministically
identity-bound for audit and replay.
