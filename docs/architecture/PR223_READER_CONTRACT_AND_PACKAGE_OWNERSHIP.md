# PR223 Reader Contract and Execution Package Ownership

## Ownership

| Boundary | Sole owner |
|---|---|
| Writer | MT5 V14 Writer, `mt5/canonical/RP_Market_State_Writer_V14_TIME_SYNC_STANDARD_V1_COMPILE_FIX.mq5` |
| Reader | `runtime.market_state_reader.GovernedMarketStateReader` |
| Execution Package | PR189 `learning.execution_package.GovernedExecutionPackageAssemblyEngine` |
| Runtime adapter | `runtime.execution_package_bootstrap.ExecutionPackageRuntimeBootstrap` (integration only; no package authority) |

PR223 adds no Decision Context, Recommendation, Execution Package, repository,
or UUID authority. The existing runtime bootstrap passes exact PR186–PR188
records to PR189, re-consumes the unchanged PR189 artifact through PR190, and
exports only its canonical UUID.

## Canonical Writer-to-Reader contract

The matrix is derived from the V14 JSON construction block. Every listed field
is required. JSON `number` below means the Reader accepts only an actual JSON
integer or floating-point number, never `bool` or string. The Writer declares
`heartbeatUnix` as MQL5 `long` and serializes it with `IntegerToString`, so the
canonical JSON heartbeat type is integer; the Reader intentionally accepts only
that representation.

| Writer field | Writer JSON type | Reader field | Reader accepted type | Presence | Result |
|---|---|---|---|---|---|
| `producer` | string | `producer` | `str` | required | compatible |
| `producer_version` | string | `producer_version` | `str` | required | compatible |
| `schema_version` | string | `schema_version` | `str` | required | compatible |
| `source_uuid` | string | `source_uuid` | `str` | required | compatible |
| `symbol` | string | `symbol` | `str` | required | compatible |
| `timeframe` | string | `timeframe` | `str` | required | compatible |
| `time_sync` | string | `time_sync` | `str` | required | compatible |
| `heartbeat_unix` | integer | `heartbeat_unix` | `int` (not `bool`) | required | compatible |
| `sequence_id` | integer | `sequence_id` | `int` (not `bool`) | required | compatible |
| `server_time` | string | `server_time` | `str` | required | compatible |
| `bar_time` | string | `bar_time` | `str` | required | compatible |
| `bid` | number | `bid` | `int` or `float` (not `bool`) | required | compatible |
| `ask` | number | `ask` | `int` or `float` (not `bool`) | required | compatible |
| `ma50` | number | `ma50` | `int` or `float` (not `bool`) | required | compatible |
| `ma90` | number | `ma90` | `int` or `float` (not `bool`) | required | compatible |
| `ma200` | number | `ma200` | `int` or `float` (not `bool`) | required | compatible |
| `rsi` | number | `rsi` | `int` or `float` (not `bool`) | required | compatible |
| `macd_main` | number | `macd_main` | `int` or `float` (not `bool`) | required | compatible |
| `macd_signal` | number | `macd_signal` | `int` or `float` (not `bool`) | required | compatible |
| `macd_hist` | number | `macd_hist` | `int` or `float` (not `bool`) | required | compatible |
| `bb_upper` | number | `bb_upper` | `int` or `float` (not `bool`) | required | compatible |
| `bb_middle` | number | `bb_middle` | `int` or `float` (not `bool`) | required | compatible |
| `bb_lower` | number | `bb_lower` | `int` or `float` (not `bool`) | required | compatible |
| `bb3_upper` | number | `bb3_upper` | `int` or `float` (not `bool`) | required | compatible |
| `bb3_middle` | number | `bb3_middle` | `int` or `float` (not `bool`) | required | compatible |
| `bb3_lower` | number | `bb3_lower` | `int` or `float` (not `bool`) | required | compatible |
| `bb4_upper` | number | `bb4_upper` | `int` or `float` (not `bool`) | required | compatible |
| `bb4_middle` | number | `bb4_middle` | `int` or `float` (not `bool`) | required | compatible |
| `bb4_lower` | number | `bb4_lower` | `int` or `float` (not `bool`) | required | compatible |
| `buyScore` | integer | `buyScore` | `int` (not `bool`) | required | compatible |
| `sellScore` | integer | `sellScore` | `int` (not `bool`) | required | compatible |

The live V14 payload also publishes governed telemetry extension fields. The
Reader permits those extensions while preserving the required base schema; it
does not reinterpret or fabricate them. The four identity constants published
by the Writer exactly match the Reader constants: producer
`RP_AI_MT5_MARKET_STATE`, producer version `V1`, schema `1.0`, and source UUID
`dc3777c6-cf0d-5a7b-bd58-8a5c44568475`.
