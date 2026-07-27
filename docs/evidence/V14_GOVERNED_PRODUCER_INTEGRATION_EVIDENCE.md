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

## Governance and restart contract

Producer identity is compile-time owned. Telemetry is passed through typed
outputs from `RP_MT5_DIRECT_TELEMETRY_V1`; its canonical policy descriptor has
SHA-256 `15f8246a13a1dac279fd9c765ef7a57e527f3dd9999798f88a42c6bb9000571e`
and UUID `d479c5d4-fc15-5dad-911c-40fa8729aa50`. Slippage expectation is the
broker-authored execution tick granularity (`SYMBOL_TRADE_TICK_SIZE / SYMBOL_POINT`),
not spread. Sequence state is terminal-global, source-and-symbol scoped,
flushed durably, and advanced only after successful publication.

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
