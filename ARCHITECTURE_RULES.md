# ARCHITECTURE_RULES — V27 Trade Management Dashboard Architecture

## Sole authority
This document, `CURRENT_SYSTEM_STATE.md`, `DECISION_FLOW_MAP.md`, and `EMERGENCY_PATCH_POLICY.md` are the authoritative architecture documents for V27 changes.

## Mandatory subsystem separation
The runtime is separated into two independent subsystems:

1. **Subsystem A — AI Decision Engine**
   - Owns direction, bias, entry timing, market mode, position classification, and initial risk payload publication.
   - Must not own post-entry exit tuning.
   - Must not require recompilation or code edits for exit behavior tuning.

2. **Subsystem B — Trade Management Dashboard**
   - Owns post-entry open-position management.
   - Owns exit configuration, profile selection, runtime dashboard parameters, and import/export profile files.
   - Must route every effective exit decision through the Exit Authority Manager.

## V27 no-touch AI boundary
V27 trade-management optimization must not modify:
- AI direction logic
- Bias engine
- Entry engine
- Signal generation
- Market classification

## Exit authority rule
Only one effective exit owner is allowed at a time. Priority is:
`EMERGENCY_EXIT -> HARD_LOSS_CAP -> PROFIT_LOCK -> BREAKEVEN -> TRAILING -> RUNNER -> TIME_EXIT`.

## Runtime configuration rule
Dashboard parameters must be loaded at runtime from JSON profile files, with backward-compatible defaults if files are missing or malformed.
