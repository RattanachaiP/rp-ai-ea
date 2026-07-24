# PR158 — Knowledge Runtime Gateway

`runtime.knowledge_gateway.KnowledgeRuntimeGateway` is the sole Runtime-facing
read boundary for Active Knowledge. Runtime consumers never receive Registry
implementation objects. They receive immutable `RuntimeKnowledgeDescriptor`
records inside a versioned `KnowledgeRuntimeSnapshot`.

The gateway depends on the structural `ActiveKnowledgeReader` Protocol rather
than the concrete Active Knowledge Registry. Production wiring injects the
Registry or another conforming adapter outside the Runtime package.

Every read invokes the upstream fail-closed projection. Corruption therefore
propagates and a cached snapshot is never used as a stale fallback. The cache
preserves immutable object identity only when the verified registry digest is
unchanged; it is not a substitute for Registry replay.

Before exposure, the gateway validates uniqueness of knowledge UUID, activation
UUID, semantic identity, and event sequence. Duplicate or malformed ACTIVE
projections fail closed with `RUNTIME_KNOWLEDGE_PROJECTION_INVALID`.

The gateway tracks the highest observed Registry sequence. A later projection
with a lower sequence fails closed with
`ACTIVE_KNOWLEDGE_REGISTRY_ROLLBACK_DETECTED`.

Schema and configuration versions use strict ASCII Semantic Version parsing.
Unsupported entries are excluded without interpretation and reported in the
immutable `rejected` mapping.

Snapshot identity includes:

- Registry digest
- Gateway contract version
- Compatibility policy version
- Supported schema majors
- Supported configuration majors
- Highest Registry sequence
- Source event count
- Accepted Runtime descriptors
- Rejection reasons

This boundary owns no qualification, promotion, lifecycle transition, strategy,
risk, trading, broker, MT5, order, or execution behavior.
