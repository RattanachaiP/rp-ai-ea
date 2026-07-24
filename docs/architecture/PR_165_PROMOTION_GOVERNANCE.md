# PR165 — Promotion Governance

`learning.promotion_governance` is the sole policy authorization layer between
qualification and PR156. It consumes only caller-supplied qualification decision,
evidence, and summary artifacts. It never imports runtime, registry, activation,
or PR156 execution code.

Promotion states are exactly `APPROVED`, `REJECTED`, `DEFERRED`, and `EXPIRED`.
The default policy is `MANUAL_ONLY`: a qualified candidate remains deferred until
an explicit approver and timezone-aware approval timestamp are supplied. Approved
audits are canonical JSON, atomically appended beneath
`learning_data/promotion_history/`; existing audit files are never replaced.

An approved `PromotionPackage` is rollout preparation only. PR156 remains the
execution authority and activation scheduling remains a separate controlled step.
