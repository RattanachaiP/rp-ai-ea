# PR207 Passive Knowledge Formation Contract

PR207 is the evidence-qualification stage immediately after PR206 Pattern
Discovery. It consumes only an immutable `Pattern` and the exact PR205
`OutcomeAttribution`, PR203 `CompletedTradeEvent`, and PR201
`LiveOutcomeRecord` records referenced by that pattern. It reconstructs the
pattern from those sources before qualification. Missing, corrupt, duplicate,
incomplete, mismatched, or mixed-replay input fails closed.

Qualification uses only declared deterministic thresholds. A supported pattern
meeting the qualified sample-count and configured-confidence thresholds is
`QUALIFIED`; one that remains above the candidate confidence floor is
`CANDIDATE`; an unsupported pattern type or one below that floor is `REJECTED`.
Configured confidence is PR206 configuration metadata, not a calculated
probability. PR207 performs no predictive inference, scoring, optimisation, or
subjective assessment.

Every immutable `CandidateKnowledge` contains its deterministic knowledge UUID,
parent pattern UUID, status, sorted rationale codes, exact evidence references,
deterministic qualification timestamp, replay identity, contract version,
canonical serialization, and SHA-256 integrity digest. Replaying identical
evidence and policy produces the identical object, UUID, serialization, and
digest.

`KnowledgeRepository` atomically appends canonical JSON under
`operational_evidence/candidate_knowledge/`. File and directory data are fsync
protected; an existing deterministic identity is rejected even when its bytes
are identical. Records are never updated, repaired, or overwritten.

Knowledge Formation is the sole producer of candidate knowledge for future
adaptive systems. It has no Runtime, Strategy, ExecutionContext, governance,
broker, order, position, exit, recommendation, optimisation, or execution
authority and cannot modify operational evidence.
