# PR159 — Knowledge Applicability Engine

`learning.applicability.KnowledgeApplicabilityEngine` is a read-only,
deterministic evaluator between a Gateway Snapshot and the Decision Engine. It
imports neither the Active Knowledge Registry nor learning lifecycle,
promotion, governance, analytics, decision, risk, execution, broker, or MT5
components.

The engine validates the immutable Gateway Snapshot digest and its schema and
configuration versions before any candidate is evaluated. It then validates
runtime session and regime, rejects duplicate candidate UUIDs, evaluates symbol,
session, timeframe, regime, execution-profile, runtime-version, and feature
compatibility, and emits stable reason codes. Invalid inputs fail closed: no
partial report is returned.

Applicable items expose only UUID, semantic identity, score, priority,
confidence, matching factors, reason codes, snapshot digest, and registry
sequence scalar provenance. Conflicts are resolved to one winner per semantic
identity by priority, score, confidence, and stable identity tie-breakers.
Reports are immutable and can be persisted append-only under
`learning_data/applicability_reports/report_<uuid>.json` without modifying the
Gateway Snapshot or Registry.
