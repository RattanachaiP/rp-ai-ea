# PR154 — Knowledge Qualification Engine

`learning.qualification` is a deterministic, read-only readiness evaluator. Its only evaluation input is a caller-supplied Knowledge Control Plane snapshot; it neither creates a control plane nor accesses repositories, governance, lifecycle, analytics, policy, runtime, executor, broker, or decision modules.

`KnowledgeQualificationEngine.qualify()`, `evaluate()`, `explain()`, and `summary()` evaluate policy eligibility, governance, verified lifecycle state, analytics stability/conflict completeness, control-plane health, lineage, snapshot integrity, schema versions, and configuration versions. Scoring weights and thresholds are explicit in immutable, versioned `QualificationConfig`.

Reports have deterministic UUIDs derived from the snapshot digest and configuration, include all PASS/WARNING/FAIL explanations, and have one of `QUALIFIED`, `CONDITIONALLY_QUALIFIED`, `NOT_QUALIFIED`, `INSUFFICIENT_INFORMATION`, or `INVALID_SNAPSHOT` statuses. Qualification has no promotion or activation authority.

`QualificationStorage` persists an immutable, atomic, append-only JSON report at `learning_data/qualification/qualification_<uuid>.json`; same-content replays are idempotent and differing content at the same identity is rejected.
