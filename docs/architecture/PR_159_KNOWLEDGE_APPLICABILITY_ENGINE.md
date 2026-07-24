# PR159 — Runtime Knowledge Applicability Engine

`runtime.knowledge_applicability.KnowledgeApplicabilityEngine` is a deterministic,
stateless Runtime consumer of the PR158 `KnowledgeRuntimeSnapshot`. It does not
create a second Gateway DTO, read the Active Knowledge Registry, or own lifecycle,
promotion, governance, decision, risk, broker, MT5, or execution behavior.

Architecture:

```text
Active Knowledge Registry
        ↓
PR158 Knowledge Runtime Gateway
        ↓
KnowledgeRuntimeSnapshot / RuntimeKnowledgeDescriptor
        ↓
PR159 Runtime Knowledge Applicability Engine
        ↓
Immutable ApplicabilityReport
        ↓
Runtime decision consumer
```

Applicability constraints are read from each Runtime descriptor's immutable
metadata. Exact and explicit `("*",)` wildcard matching are supported for symbol,
session, timeframe, market regime, volatility class, trend state, execution
profile, and Runtime version. Exact matches produce a specificity score; conflict
resolution is priority, specificity, confidence, then stable knowledge UUID.

The engine validates Gateway contract and compatibility-policy semantic-version
majors, known session/regime values, candidate invariants, finite confidence, and
required feature flags. It owns no mutable last-report state. Reports recompute and
verify their digest and deterministic UUID during construction.

`runtime.applicability_storage.ApplicabilityReportRepository` provides durable,
append-only persistence under `learning_data/applicability_reports/`. Writes use a
unique temporary file, file fsync, atomic hard-link publication, collision byte
verification, cleanup, and directory fsync where supported. Existing content can
never be silently replaced.

`learning.applicability` remains only a compatibility facade; Runtime owns the
contracts, evaluation semantics, and report persistence boundary.
