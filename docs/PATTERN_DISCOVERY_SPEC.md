# PR206 Pattern Discovery Contract

PR206 is a passive operational-evidence observer. It consumes only immutable
PR205 `OutcomeAttribution` records and their exact PR203 `CompletedTradeEvent`
and PR201 `LiveOutcomeRecord` parents. Each attribution is reconstructed from
those parents before discovery; missing, corrupt, mismatched, duplicate, or
mixed-replay evidence fails closed.

The engine describes winning and losing trade characteristics, UTC entry and
exit clusters, configured stop-loss and take-profit distributions, duration and
latency distributions, manual-intervention frequency, and replay consistency.
It makes no prediction or recommendation and performs no optimisation.
Candidate groups below the configured sample threshold are not emitted. A
whole discovery request below that threshold is rejected.

Every immutable `Pattern` contains a deterministic UUID, canonically ordered
source attribution UUIDs, sample count, configured confidence level,
observation window, factual supporting evidence, deterministic discovery
timestamp, replay identity, and SHA-256 digest. Replaying identical evidence
and configuration produces identical records.

`configured_confidence_level` is configuration metadata recording the target
confidence level supplied to discovery. It is not a calculated confidence
estimate, statistical score, probability, effect size, stability measure, or
claim about the discovered pattern. PR206 does not infer any such value.

`PatternRepository` atomically appends canonical JSON under
`operational_evidence/patterns/`. Existing identities are rejected even when
their bytes are identical; records are never updated or repaired. Pattern
Discovery is the sole producer of candidate operational knowledge, but the
patterns themselves have no Runtime, Strategy, governance, broker, order,
position, exit, optimisation, recommendation, or execution authority.
