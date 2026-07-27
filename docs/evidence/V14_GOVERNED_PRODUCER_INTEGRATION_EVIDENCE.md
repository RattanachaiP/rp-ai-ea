# Canonical V14 governed producer integration evidence

## Source custody

The integration started from merge `f0272d298085c2f58153265378f0964f858411d0` on `codex-dev`.
The imported, unmodified canonical source had:

- path: `mt5/canonical/RP_Market_State_Writer_V14_TIME_SYNC_STANDARD_V1_COMPILE_FIX.mq5`
- SHA-256: `d4788ffedcea1f46e013b797311acb44d5fffbf577643c37a38bf79c2c5a8d91`
- Git blob (`git hash-object`): `25e5667b0145d32198bc6ac5555d44973a8797b1`

## Before/after schema evidence

The ordered pre-integration fields are:

`symbol`, `timeframe`, `time_sync`, `heartbeat_unix`, `sequence_id`,
`server_time`, `bar_time`, `bid`, `ask`, `ma50`, `ma90`, `ma200`, `rsi`,
`macd_main`, `macd_signal`, `macd_hist`, `bb_upper`, `bb_middle`, `bb_lower`,
`bb3_upper`, `bb3_middle`, `bb3_lower`, `bb4_upper`, `bb4_middle`, `bb4_lower`,
`buyScore`, `sellScore`.

Every pre-integration field remains once, in the same relative order. The
integration adds the four fixed identity fields, the four direct telemetry
fields required by the PR212 consumer, and four telemetry-policy provenance
fields. `tests/test_mt5_market_state_producer_contract.py` extracts the actual
builder keys and enforces the ordered-subset and no-duplicate-key properties.
It also pins all 15 indicator reads and every pre-existing score formula.

## Governance, telemetry, and restart contract

Producer identity is compile-time owned. Review of the unchanged PR212 consumer
shows that `slippage_expectation` must be a finite, non-negative numeric producer
observation; the consumer does not authorize execution tick granularity as a
slippage proxy. The integration therefore no longer uses
`SYMBOL_TRADE_TICK_SIZE / SYMBOL_POINT`. `RP_MT5_MODELED_TELEMETRY_V2` models
expected slippage as an EWMA (alpha 0.2) of absolute successive live-tick
mid-price movements in points and publishes nothing until at least one observed
transition exists. Its canonical policy descriptor has SHA-256
`4a94734a04a574ecc58784da93e8dfe6c04e13726d1a7158b634db8d6c29998f` and UUID
`deb04c7b-be67-5b44-a00c-02ece75326bd`.

Tick validity fails closed for inverted/non-positive prices and tick ages outside
0..5 seconds. Session quality is `1.0` only for `FULL`, `0.5` for `LONGONLY` or
`SHORTONLY`, and `0.0` for `CLOSEONLY` or `DISABLED`. Liquidity quality is `1.0`
through 20 spread points, degrades linearly, is `0.0` at 50 points, and is also
`0.0` when the session cannot open positions.

The explicit sequence failure policy is **durable reservation before
publication, with gaps permitted**. If reservation fails, publication does not
start. If publication fails after reservation, that ID remains consumed and the
next attempt uses a greater ID. Thus an escaped ID cannot be reused. The
regression suite checks source ordering and exercises reservation failure,
publication failure, subsequent success, uniqueness, and monotonicity in the
policy state machine. Terminal-global state remains source-and-symbol scoped and
is flushed on every reservation.

## MetaEditor compile evidence

MetaEditor is not installed in the Linux integration environment. No compile
result is fabricated. Production promotion remains gated on compiling this
exact committed `.mq5` in MetaEditor and attaching its `0 errors, 0 warnings`
build log here. The Python contract suite is regression evidence only and is
not a substitute for that required compiler evidence.

The MetaEditor command attempted in the integration environment was:

```text
MetaEditor64.exe /compile:mt5/canonical/RP_Market_State_Writer_V14_TIME_SYNC_STANDARD_V1_COMPILE_FIX.mq5 /log:metaeditor-v14.log
/bin/bash: MetaEditor64.exe: command not found
```
