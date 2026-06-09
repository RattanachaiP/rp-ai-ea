# DECISION_FLOW_MAP — Runtime Lineage and Participation Governance Flow

## Authoritative lineage
`codex-dev` (single source of truth)

## Governance flow
1. AI room proposes reference patch
2. Codex merges into authoritative code review stream
3. `codex-dev` verification
4. Test validation
5. Approved LIVE promotion

## Runtime execution path (current)
`bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py`
-> reads `market_state.json`
-> builds directional decision payload
-> applies entry-quality / NOVA / candle / exhaustion / structure / timing / location layers
-> applies V26.4.7 participation restoration
-> applies compatibility/validation layers
-> injects runtime identity metadata
-> atomically writes `decision.json`

## V26.4.7 directional authority chain
1. Hard safety blocks remain final authority.
2. Valid directional bias and score context are preserved through governance layers.
3. Weak momentum becomes a confidence penalty rather than a hard directional erase.
4. Cooldown, low-confidence, and timing waits are represented as finite `WAIT_VALID` recovery states.
5. `WAIT_VALID` timeout releases controlled participation through `EXECUTE_CAUTIOUS`.
6. `TRANSITION_WAIT` has a maximum duration and releases instead of recursively suppressing.
7. Final payload normalization preserves one outcome chain: safety block, finite wait, cautious execution, normal execution, or aggressive execution.

## Migration target (deferred-safe path)
Target file name: `bridge/ai_decision_engine_xauusd_live.py`

Recommended safe migration sequence:
1. Introduce `ai_decision_engine_xauusd_live.py` as thin launcher importing current runtime module.
2. Verify parity in decision outputs and startup identity logs.
3. Update operational launch scripts to point to `_live.py`.
4. Keep previous file as rollback reference until burn-in window passes.
