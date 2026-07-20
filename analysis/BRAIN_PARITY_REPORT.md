# Brain Phase 1 parity report

## Result

**PASS.** The authoritative V26 runtime was compared with its `HEAD` baseline using deterministic market-state fixtures. The Phase 1 boundaries return their input object unchanged and do not publish stage metadata. No `decision.json` file was written during this comparison.

## Compared runtime

- Baseline: `HEAD:bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py`.
- Candidate SHA-256: `13b3ebf41233a98626a6b74b298349db7f61c41a59e378ca0af826da9ab6a89d`.
- Scope: internal Python call boundaries only; no MT5 or dashboard files were changed.

## Fixture results

| Fixture | Result | Decision | Entry | SL | TP | Confidence | Probability |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `invalid_bid` | PASS | `NO_TRADE` | `` | `` | `` | `` | `` |
| `invalid_ma50` | PASS | `NO_TRADE` | `` | `` | `` | `` | `` |
| `equal_score` | PASS | `NO_TRADE` | `` | `` | `` | `` | `` |

## Validation method

For each fixture, the script compares the complete `build_decision()` dictionary from the parent source, the candidate source, and the candidate source after Market Perception, Market Understanding, and Market Reasoning. It then passes that same candidate decision through the remaining identity boundaries. It also explicitly compares decision/action/bias, entry, SL, TP, confidence, and probability fields. Market Reasoning is private and unwraps the original market-state dictionary by identity before the candidate build call. The complete payload equality check confirms `decision.json`-schema parity for the deterministic decision construction path; the existing atomic writer is called with the same dictionary and is otherwise unchanged.
