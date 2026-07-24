# PR156 — Promotion Authority

`learning.promotion_authority` is the Knowledge Platform's execution-only promotion authority. It consumes a supplied, signed `PromotionDecisionReport`; it does not query the repository, qualification, analytics, governance, control plane, or decision engine.

Only an `APPROVED` `PROMOTE` report is executable. Validation is fail-closed for missing reports, UUIDs, digests, configuration versions, signatures, schema versions, and freshness. Candidate-scoped filesystem locks and decision-UUID record lookup provide duplicate-execution protection.

The authority requests the independent Lifecycle Transition Service to make the `VERIFIED -> ACTIVE` transition; it does not mutate lifecycle state itself. It writes immutable, atomic, append-only promotion records to `learning_data/promotion_records/record_<uuid>.json`. Failed lifecycle execution discards the uncommitted audit staging record and invokes an optional lifecycle rollback hook.

The public API is deliberately limited to `execute()`, `validate()`, `rollback()`, and `history()`. It evaluates no knowledge and does not import runtime, trading, broker, analytics, qualification, governance, control-plane, or decision-engine modules.
