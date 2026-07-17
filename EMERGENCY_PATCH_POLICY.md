# EMERGENCY_PATCH_POLICY — V27

Emergency patches may alter post-entry trade management only when the change is implemented through the Trade Management Dashboard runtime configuration layer or through the Exit Authority Manager contract.

Emergency patches must not redesign AI direction, bias, entry timing, signal generation, or market classification. If an emergency requires an architectural exception, update the four authority documents before modifying runtime code.

All emergency exit behavior must preserve one effective exit owner and must publish dashboard profile metadata in `decision.json` for auditability.

## V28 rebuild boundary

The V28 thinking-model rebuild is not an emergency patch. Emergency-patch
authority cannot be used to implement, tune, or bypass the pending V28 decision
philosophy. Until explicit approval of `docs/v28/V28_DECISION_PHILOSOPHY.md`
and `docs/v28/V28_EXPECTANCY_FIRST_ARCHITECTURE_ADDENDUM.md`, no V28 runtime
changes are authorized and no V27 filters, cooldowns, waits, score adjustments,
patch stacks, or runtime layers may be introduced.
