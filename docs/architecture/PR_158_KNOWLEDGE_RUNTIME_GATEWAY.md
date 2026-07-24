# PR158 — Knowledge Runtime Gateway

`runtime.knowledge_gateway.KnowledgeRuntimeGateway` is the sole Runtime-facing
read boundary for Active Knowledge. Runtime consumers receive only immutable,
compatible `KnowledgeRuntimeSnapshot` objects and must not read the Active
Knowledge Registry directly.

The gateway owns Registry projection reads, trusted receipt/projection validation
(delegated to the Registry's fail-closed replay), ACTIVE lookup, cache management,
schema/configuration major-version compatibility, and snapshot digests. A registry
read failure always propagates: it never substitutes a previously cached snapshot.

Unsupported ACTIVE entries are excluded without interpretation and are reported by
knowledge UUID in the snapshot's immutable `rejected` mapping. Runtime is not
permitted to treat such entries as compatible.

This boundary owns no decision, risk, trading, broker, MT5, or execution behavior.
