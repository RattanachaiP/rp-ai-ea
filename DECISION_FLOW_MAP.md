# DECISION_FLOW_MAP — Runtime Lineage and Governance Flow

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
-> builds decision payload
-> applies compatibility/validation layers
-> injects runtime identity metadata
-> atomically writes `decision.json`

## Migration target (deferred-safe path)
Target file name: `bridge/ai_decision_engine_xauusd_live.py`

Recommended safe migration sequence:
1. Introduce `ai_decision_engine_xauusd_live.py` as thin launcher importing current runtime module.
2. Verify parity in decision outputs and startup identity logs.
3. Update operational launch scripts to point to `_live.py`.
4. Keep previous file as rollback reference until burn-in window passes.
