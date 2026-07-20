# Brain Phase 1 parity report

## Result

**PASS.** The authoritative V26 runtime was compared with its `HEAD` baseline using deterministic market-state fixtures. The Phase 1 boundaries return their input object unchanged and do not publish stage metadata. No `decision.json` file was written during this comparison.

## Compared runtime

- Baseline: `HEAD:bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py`.
- Candidate SHA-256: `28f9a6921b85beae9f10e142edfa0c2962d965adb86282f9bbc04829187db968`.
- Scope: internal Python call boundaries only; no MT5 or dashboard files were changed.

## Fixture results

| Fixture | Result | Decision | Entry | SL | TP | Confidence | Probability |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `invalid_bid` | PASS | `NO_TRADE` | `` | `` | `` | `` | `` |
| `invalid_ma50` | PASS | `NO_TRADE` | `` | `` | `` | `` | `` |
| `equal_score` | PASS | `NO_TRADE` | `` | `` | `` | `` | `` |

## Validation method

For each fixture, the script compares the complete `build_decision()` dictionary from the parent source, the candidate source, and the candidate source after Market Reasoning, Probability Engine, Expected Value Engine, and Position Intelligence boundaries. It also explicitly compares decision/action/bias, entry, SL, TP, confidence, and probability fields. Market Perception and Market Understanding are exercised before the candidate build call. Because every stage is an identity wrapper by contract, the complete payload equality check confirms payload and `decision.json`-schema parity for the deterministic decision construction path; the existing atomic writer is called with the same dictionary and is otherwise unchanged.
