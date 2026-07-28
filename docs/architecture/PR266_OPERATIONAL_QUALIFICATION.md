# PR266 V28 Operational Qualification

## Authority and frozen boundaries

PR266 is a read-only qualification layer above the immutable PR260–PR265 pipeline. It
has no broker, `OrderSend`, mutation, recovery, promotion, decision, or risk authority.
V27 remains the only production execution authority. The highest possible output is
**READY FOR HUMAN REVIEW**, never production authorization.

## Governed policy

Every campaign, run, registry version, component report, statistics report, and final
report binds the exact immutable `QualificationPolicy` identity. The identity covers
policy name/version, minimum duration and run/cohort counts, heartbeat gap and sequence
rules, delivery failure limit, consecutive stable-campaign count, expiry interval, and
the complete recommendation transition table. Component APIs do not accept caller-
selected thresholds.

## Authoritative run schema

A qualification run separately identifies the run, deterministic scenario/fixture,
normalized input projection, expected semantic output projection, and PR265 campaign.
It directly embeds and integrity-checks the PR265 pipeline, delivery, and certification
reports plus the published plan, delivery receipt, runtime-health snapshot/sample, and
explicit recovery evidence. It also binds symbol, environment, runtime sequence,
evaluation time, exact policy, and previous-run identity. Caller-manufactured success
booleans do not exist.

Scenario-equivalent runs deliberately have distinct PR265 certification, publication,
delivery, sequence, evaluation-time, and run identities. Replay compares normalized
scenario inputs and semantic output projections rather than full certification hashes.
Reusing a certification artifact for multiple runs is rejected.

## Long-duration and runtime qualification

Campaign construction enforces policy-defined duration, evidence count and density,
BUY/SELL/HOLD cohort coverage, chronological evaluation time, strict runtime sequence,
scenario family, symbol/environment consistency, run lineage, unique PR265 campaigns,
and exact expiry. Runtime monitoring uses the replay-verified `RuntimeHealthSnapshot`
and its heartbeat timestamp—not run observation time—to verify heartbeat chronology,
maximum gaps, sequence continuity, health, source, environment, and policy lineage.

Delivery reliability is evaluated as a conjunction per run: publication integrity,
pipeline validation, delivery validation, replay validation, aggregate certification,
delivered receipt, and absence of recovery must all pass on that same run. Failed runs
are counted directly and assessed against the governed policy rate.

## Registry, statistics, and recommendation

Each immutable registry version binds generation, prior registry identity, current
registry identity, append operation identity, appended campaign identity/time, and
policy. Registry construction rejects duplicates, broken campaign lineage, overlaps,
and policy mismatches. `active_at` applies `started_at <= at < expires_at`.

Statistics consume one verified registry, compare parsed UTC datetimes, and emit
canonical UTC timestamps. The final report revalidates all nested identities and exact
campaign, policy, PR265 family, symbol, environment, evaluation-window, run-count, and
statistics coverage bindings. Expired or future campaigns fail. Recommendations follow
only the policy transition table; instability, inconsistency, corruption, insufficient
consecutive history, or forbidden recovery fails closed.
