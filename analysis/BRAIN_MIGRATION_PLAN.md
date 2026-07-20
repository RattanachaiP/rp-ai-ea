# RP AI Brain migration plan

## Non-negotiable preconditions

This is a plan only. It causes **no runtime behavior change**. Existing
governance says the V28 thinking-model rebuild is proposal-only pending explicit
approval. In addition, the required `brain/` architecture documents are absent
from this checkout. Therefore **no Brain implementation phase may start** until
all of the following are true:

1. The missing Brain documents, especially `brain/DATA_CONTRACT.md`, are made
   available in the repository or supplied as authoritative source material.
2. The V28 philosophy and addendum receive the approval required by
   `ARCHITECTURE_RULES.md` and `CURRENT_SYSTEM_STATE.md`.
3. The owner, producer code/configuration, schema/version, and representative
   fixtures for live `market_state.json` are identified.
4. The deployed MT5 attachment/executor identity is verified outside this
   repository; no assumption may be made between the V27 dashboard and V28/V29
   MQL files.

## Incremental order

| Phase | Work and exact tracked files | Runtime/contract effect | Exit criteria |
| --- | --- | --- | --- |
| 0 — approval and evidence | Restore/provide the required `brain/` documents. Add only evidence-backed fixtures/tests after the producer is known; no filename is proposed here because neither the producer nor its schema is tracked. | None. | Approved architecture, data contract, and market-state ownership. |
| 1 — characterize the current contract | Add contract/parity tests to the existing `tests/` suite for the authoritative V26 engine and its emitted payload. The exact test file names must follow the supplied contract; no new name is proposed before it exists. Inspect only `bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py`, `mt5/v28/RP_AI_Executor_V28_CleanCore.mq5`, and `mt5/RP_AI_TradeManagementDashboard_V27_1.mq5` for current field consumption. | None; preserve byte/semantic compatibility of `decision.json`. | Recorded fixtures cover TRADE, NO_TRADE, WAIT, stale input, invalid input, and dashboard-profile cases. |
| 2 — shadow the approved Brain pipeline | Use the existing non-authoritative `bridge/v28/clean_core.py`, `bridge/v28/payload_contract.py`, `bridge/v28/dashboard_contract.py`, and `bridge/v28/shadow_launcher.py` only if their approved responsibilities match the supplied Brain contract. Change these existing files and their existing tests (`tests/test_v28_clean_core.py`) rather than inventing a parallel runtime directory. Publish shadow output only to the already-existing `v28_shadow_decision.json` path used by `shadow_launcher.py`. | No change to `decision.json`, MT5 executor, or trade management. | Deterministic replay and parity/difference reports explain every V26-versus-shadow divergence. |
| 3 — stage extraction behind an adapter | After shadow parity and an approved contract, change the authoritative `bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py` only to call approved stage adapters while retaining its current `read_market()` and `write_decision()` boundaries. Change/add tests in the existing `tests/` tree. Create implementation modules only when the approved Brain documentation names their directory/file location; this audit cannot name them without inventing paths. | `decision.json` remains unchanged; MT5 files are untouched. | Existing V26 regression tests plus contract/replay tests are green and payload parity is accepted. |
| 4 — controlled activation | Change the operational launcher only after its actual tracked identity is discovered. The current tree has no authoritative Python runtime launch script; therefore no exact launcher file can be listed. Keep `bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py` unchanged as the rollback runtime. | A separately approved cutover only; no MQL executor or trade-management change in this phase. | Canary/shadow observations, fresh-data checks, executor contract checks, and rollback drill pass. |
| 5 — learning promotion | Change `analysis/trade_statistics.py` and `analysis/trade_autopsy_engine.py` only after an approved learning contract defines immutable input records, validation gates, and promotion authority. Do not connect their outputs to live V26 behavior before that approval. | Offline evidence first; live feedback remains disabled. | Reproducible reports, lineage, calibration/EV acceptance criteria, and manual promotion/rollback procedure. |

## Backward-compatibility strategy

* Keep the V26 engine, all legacy engines, all MQL files, and existing runtime
  filenames in place. Do not rename or delete them.
* Keep `market_state.json` read behavior and `decision.json` publication path
  unchanged until an adapter is validated.
* Treat `ensure_ea_v17_compat_fields()` and existing aliases as the current
  compatibility boundary. A future Brain payload must be translated there,
  not supplied directly to MT5.
* Run new intelligence in shadow mode first using the existing V28 shadow
  launcher/path. It must not write `decision.json` or place trades.
* Keep dashboard ownership of post-entry exits and executor ownership limited
  to payload/schema/freshness/broker safety. Do not modify MT5 executor or
  trade-management behavior as part of the Brain extraction.

## Testing strategy

1. **Static/topology checks:** assert the authoritative V26 path, input path,
   output path, and absence/presence of required data-contract fields.
2. **Fixture replay:** replay producer-authenticated market states through V26
   and the shadow Brain pipeline, compare semantic decision, direction, entry
   permission, price/risk, freshness, and identity fields.
3. **Payload compatibility:** run the existing V28 payload contract tests and
   direct field-consumption tests against both MQL readers without modifying
   MQL behavior.
4. **Safety regression:** retain stale-data, invalid payload, hard-risk,
   cooldown/wait, and atomic-publication coverage.
5. **Learning validation:** calculate calibration and expected-value metrics on
   held-out, versioned closed-trade data; do not promote a model on the same
   data used to define it.
6. **Shadow/canary observation:** compare outputs before any cutover; record
   every divergence with source market-state sequence ID and contract version.

## Rollback strategy

* Shadow phases have no live effect: stop the shadow launcher and retain V26
  publication unchanged.
* For a future approved activation, restore the verified current launcher to
  `bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py` and
  preserve the previous decision payload adapter.
* Never use a rollback to overwrite live decision history or alter open-position
  management. The V27 dashboard continues to manage already-open positions
  under its existing exit-authority rules.
* Trigger rollback on contract validation failure, stale/freshness regression,
  unexplained payload divergence, executor hard-safety regression, or breach
  of the approved decision/EV acceptance thresholds.

## Recommended first implementation task

**Do not implement a Brain module yet.** First restore/provide the missing
`brain/` source documents and the authoritative `market_state.json` producer
schema, then approve the V28 architecture gate. The first code task after those
preconditions should be a non-live, fixture-backed contract/parity test for the
existing V26 `read_market()` -> `write_decision()` boundary; it must leave
`decision.json`, MT5 executor behavior, and trade management unchanged.
