# EMERGENCY_PATCH_POLICY — V27

Emergency patches may alter post-entry trade management only when the change is implemented through the Trade Management Dashboard runtime configuration layer or through the Exit Authority Manager contract.

Emergency patches must not redesign AI direction, bias, entry timing, signal generation, or market classification. If an emergency requires an architectural exception, update the four authority documents before modifying runtime code.

All emergency exit behavior must preserve one effective exit owner and must publish dashboard profile metadata in `decision.json` for auditability.
