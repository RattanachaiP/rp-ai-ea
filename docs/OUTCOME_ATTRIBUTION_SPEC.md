# PR205 Outcome Attribution Contract

PR205 is a passive post-completion analysis boundary. It consumes one canonical
`CompletedTradeEvent` and the corresponding immutable `LiveOutcomeRecord`. It
does not query a broker and has no dependency on Runtime, Strategy,
`ExecutionContext`, Executor, broker-safety, position-management, exit, or
`OrderSend` implementation code.

## Deterministic record

For each verified source pair, `OutcomeAttributionEngine` emits one immutable
`OutcomeAttribution`. Its UUID is UUIDv5-derived solely from the parent
`CompletedTradeEvent` UUID. Its timestamp is the event's immutable capture
timestamp, and its canonical body is SHA-256 integrity-bound. Thus replaying the
same operational evidence produces the same record byte-for-byte.

The outcome classification is only `PROFITABLE`, `LOSS`, or `BREAKEVEN`, based
on the observed final net profit. Supporting evidence reports strategy
alignment, entry and exit timing, stop-loss and take-profit outcome, manual
intervention, risk profile, duration, latency, and replay verification. When a
source contract does not contain a fact, the record says `UNAVAILABLE` or
`NOT_PRESENT_IN_EVIDENCE`; it does not infer or repair the fact.

`COMPLETE_OPERATIONAL_EVIDENCE` describes successful integrity and lineage
verification of both required source records. It is not a probability, score,
recommendation, quality judgment, or authorization.

## Persistence and authority

`OutcomeAttributionRepository` atomically appends canonical records beneath
`operational_evidence/outcome_attributions/`. Existing identities are rejected,
including byte-identical duplicates; records are never updated or replaced.

Outcome attribution is the authoritative descriptive input for future Pattern
Discovery. Pattern Discovery is not implemented by PR205. Attribution cannot
recommend, learn, optimize, publish decisions, mutate evidence or runtime
state, contact a broker, or alter any execution behavior.
