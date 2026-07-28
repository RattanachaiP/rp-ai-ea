# PR233 MT5 Writer Status

## Observation result

**NOT VERIFIED / NOT ATTACHED IN THIS EXECUTION ENVIRONMENT.** The evidence run was performed in a Linux container. No `terminal64`, MetaTrader, or Wine-hosted terminal process was running; neither a Wine executable nor an MT5 terminal executable was available. Therefore an authentic chart attachment cannot be asserted.

| Required fact | Runtime-observed value |
|---|---|
| Symbol | **UNAVAILABLE** — no live MT5 chart/Writer runtime |
| Timeframe | **UNAVAILABLE** — no live MT5 chart/Writer runtime |
| EA version | **UNAVAILABLE at runtime** — the canonical source artifact is named V14 and declares MQL property version `1.20`, but no loaded EA instance was observed |
| Terminal build | **UNAVAILABLE** — no MT5 terminal process/binary |

The source artifact's configured signal timeframe is `PERIOD_M3` and its default publication interval is one second. These are static source settings, not evidence of the chart, loaded inputs, or live publication. `02_MARKET_STATE_STREAM.log` is the runtime host/process/file evidence.
