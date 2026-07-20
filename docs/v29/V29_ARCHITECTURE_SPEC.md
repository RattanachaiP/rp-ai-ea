# V29 Architecture Specification — AI Entry Intelligence + Progressive TP/BE

## Scope lock

V29 changes exactly two bounded capabilities: **AI Entry Intelligence** before a new order and **Progressive TP/BE** after an order. It does not modify V27/V28 runtime files, direction-score production, lot sizing, risk limits, dashboard ownership, brokersafety, runner logic, trailing, time exits, or deployment topology. V29 is shadow/demo-only until separately promoted.

## 1. AI Entry Intelligence

The existing upstream BUY/SELL score nominates a direction; V29 does not alter that score. A nominated direction is executable only when all three independently published observations align: (a) market structure or BB walk agrees with the direction, (b) RSI/MACD momentum agrees, and (c) location is not exhausted (RSI >=75 BUY, <=25 SELL, or an extreme BB state). The payload records each boolean and a single explicit rejection reason. This produces an auditable entry decision, not a new strategy layer or a score adjustment.

## 2. Progressive TP/BE

Initial risk (`1R`) is immutable at entry. The management authority applies exactly one uncompleted ladder action: TP1 at +1R closes 50% and moves protection to BE; TP2 at +2R closes 25% of original volume and protects +0.5R; TP3 at +3R closes the remaining scheduled 25% and protects +1R. Protection may only move in the favorable direction. There is no runner, trailing stop, time exit, averaging, or additional exit owner.

## Authority and safety

`AI Entry Intelligence -> V29 payload -> broker safety / OrderSend`; after entry, `RP_AI_ProgressiveTPBE_V29.mq5` is the sole V29 management owner. The broker retains rejection and execution safety authority. Each management action is persisted per position ticket in an MT5 terminal global variable: a completed level cannot be closed twice, and a stop cannot be loosened.

## Acceptance criteria

1. A trade is published only when all three entry confirmations pass.
2. Every rejection identifies the failed confirmation(s).
3. TP1/TP2/TP3 occur at 1R/2R/3R with 50%/25%/25% scheduled volume.
4. BE moves only after the corresponding target and never moves backwards.
5. V27/V28 files and active dashboard profiles remain unchanged.

## 3. V29.1 Entry Quality Model

V29.1 inserts a timing-only gate after the existing Direction Decision and before `TRADE` publication. `entry_quality_engine.py` accepts the already nominated `BUY` or `SELL` direction and never creates, flips, scores, or resizes it. It scores the existing structure, momentum, location, exhaustion, and market-quality observations from 0 to 100; the final `entry_score` is their deterministic unweighted mean. A score of at least 70 with no component below 60 yields `EXECUTE`; otherwise the published decision is `WAIT_FOR_BETTER_ENTRY` while retaining the exact nominated direction.

The V29 payload remains additive and schema-compatible. It now includes `entry_score`, `entry_confidence`, `waiting_reason`, and `entry_components`, in addition to the existing entry-intelligence and TP/BE fields. `entry_quality_telemetry` is a deterministic record containing direction, every component score, final score, and `EXECUTE` or `WAIT_FOR_BETTER_ENTRY`. V27 and V28 files and their runtime paths are not used or changed by this layer.
