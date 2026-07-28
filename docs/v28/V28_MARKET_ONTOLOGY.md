# V28 Market Ontology — Contract 1.0

This document governs PR261's descriptive market language. The contract schema is
`V28.MARKET_CONTEXT.1.0`; its sole parameter authority is policy
`V28_MARKET_INTELLIGENCE_POLICY` version `1.0.0`, owned by
`V28_MARKET_INTELLIGENCE`.

Every context is immutable and contains a schema version, policy identity, one
allowed state, structured evidence, an explanation, and a data-quality state of
`VALID`, `INSUFFICIENT`, `DEGRADED`, or `FAIL_CLOSED`.

| Context | Allowed states |
|---|---|
| Structure | `ADVANCING`, `DECLINING`, `RANGE`, `EXPANSION`, `UNDETERMINED` |
| Regime | `TREND`, `RANGE`, `TRANSITION`, `EXPANSION`, `VOLATILITY_SHIFT`, `UNDETERMINED` |
| Trend | `UPWARD`, `DOWNWARD`, `SIDEWAYS`, `UNDETERMINED` |
| Momentum | `ACCELERATION`, `DECELERATION`, `CONTINUATION`, `IMPULSE`, `WEAKENING`, `UNDETERMINED` |
| Volatility phase | `STABLE`, `SHIFT`, `UNDETERMINED`; evidence separately records level and phase |
| Liquidity | `OBSERVED_GEOMETRY`, `HYPOTHESIS`, `UNDETERMINED` |
| Opportunity | `PRESENT`, `ABSENT`, `UNDETERMINED` |

Liquidity output primarily states price geometry. Any liquidity interpretation is
labelled a hypothesis and carries evidence quality. Opportunity is a neutral,
non-executable market representation; it never grants direction, entry, risk, or
execution authority.

## Closed-bar evidence

Each bar requires finite OHLC values, a numeric UTC Unix `timestamp`, `closed=true`,
and `source_sequence_id` equal to the containing market snapshot. Bars must be
strictly chronological, unique, and separated by the declared timeframe. A forming,
unordered, duplicate, malformed, or wrongly spaced bar fails the entire observation
window closed. Prior and recent structure cohorts are independent and non-overlapping.
