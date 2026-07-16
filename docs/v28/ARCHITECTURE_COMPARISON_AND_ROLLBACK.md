# V28 Clean Expectancy Core: Architecture Comparison and Rollback

## Parallel architecture

V28 is an independent Python decision producer. Its path is:

`Market State Writer -> V28_CLEAN_EXPECTANCY_CORE -> atomic v28_shadow_decision.json -> (isolated demo only) V28 executor -> broker safety -> OrderSend`.

The Market State Writer remains market-data-only. Python owns direction, entry, confidence tier, size multiplier, and initial risk package. The dashboard owns post-entry management. The executor owns schema validation, broker safety, and OrderSend only.

## V27 versus V28

| Concern | V27 | V28 |
| --- | --- | --- |
| Decision path | Layered legacy/patch lineage | One core decision function |
| Entry classification | Multiple waits, gates, and normalizers | Directional score-gap entry or explicit no-trade |
| Risk profile | Historical profile-dependent behavior | Deterministic Profile_F validation baseline: +$1 TP and -$1.20 hard-loss cap per 0.01 lot |
| Exit ownership | Dashboard | Dashboard; V28 does not tune exits |
| Publication | `decision.json` | Separate V28 shadow path until isolated demo validation |
| Executor role | Legacy compatibility concerns | Contract + broker safety + OrderSend only |

## V27 logic intentionally not imported

- Soft Lock and Transition Wait stacks.
- Weak Gap, emergency participation, cooldown override, and historical emergency patch stacks.
- V15/V16/V17 entry, momentum, quality, alignment, and final-decision vetoes.
- Duplicate expectancy, entry-location, timing, and final schema gates.
- Legacy final-decision normalization and hidden profile overrides.
- Legacy BE, trailing, runner, profit-lock, scaling, pyramiding, and position-management logic.

## Validation and promotion

1. Run `python -m bridge.v28.shadow_launcher` against the market-state feed; it only writes `RP_AI_EA/shared/XAUUSD/v28_shadow_decision.json`.
2. Compare V27/V28 candidate timestamps, direction, trade rate, explicit decision reason, and risk-contract validity.
3. Use the isolated demo launcher only with `--demo-confirmation` and the V28 executor.
4. Check reliability at 30 trades; evaluate expectancy at 100; require repeatability at 300.
5. Promote only if PF > 1, expectancy > 0, gross profit exceeds gross loss, participation is at least 70%, average loss does not materially exceed average win, and equity slope is positive.

## Rollback

1. Stop the V28 shadow/demo launcher and detach `RP_AI_Executor_V28_CleanCore.mq5` from the demo chart.
2. Keep the V27 decision writer and executor configuration unchanged; V28 never writes V27's `decision.json`.
3. Archive `v28_shadow_decision.json`, demo decisions, and closed-trade evidence for analysis.
4. Restore no files to resume V27 because V28 is parallel. Do not promote a V28 payload path into a live executor without a separately approved deployment change.

## Evidence limitation

The repository's `analysis/trade_memory.csv` is empty. The report generator explicitly records unavailable replay metrics rather than inventing profitability claims.
