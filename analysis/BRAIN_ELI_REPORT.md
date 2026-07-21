# Entry Location Intelligence (ELI) — Phase 1

## Confirmed problem

Direction and momentum can be correct while the entry is late: a BUY near an exhausted swing high or a SELL near an exhausted swing low can be trapped by the ensuing reversal. ELI answers whether price is a valid location for an already-selected direction; it does not predict direction.

## Domain boundary

`brain/entry_location_intelligence.py` is pure, deterministic, in-memory Python. It has no MT5 or broker calls, writer/executor imports, runtime wiring, timers, or `decision.json` changes. APC is intentionally unchanged.

## Inputs and outputs

The input includes direction, current/swing/impulse prices, ATR, pullback and structure evidence, liquidity sweeps, support/resistance, target, invalidation, and confidence. The immutable assessment returns permission, an explicit state, 0–100 score, explainable component scores/reasons, swing position, ATR extension, and RR.

## Calculations and states

Swing position is `(current - swing_low) / (swing_high - swing_low)`: 0 is the low and 1 is the high. BUY at/above 0.90 and SELL at/below 0.10 hard-block. Directional ATR extension is `max(0, directional impulse / ATR)`; 2.0 ATR requires a pullback and 2.5 ATR hard-blocks unless pullback and continuation structure are confirmed. A confirmed low-extension trend start is a bounded breakout exception, not momentum-only permission.

Pullback states distinguish no pullback, unconfirmed pullback, confirmed pullback, and confirmed continuation. Opposing liquidity sweeps require continuation confirmation. RR uses directional reward/risk from entry, target, and invalidation; non-positive geometry or RR below 1.20 blocks.

## Score, safety, and future integration

The score sums bounded swing-location, ATR-extension, pullback, structure, liquidity, RR, support/resistance-distance, and confidence components. Confidence is informational only and cannot override any hard block. Invalid inputs, swing/ATR, target/invalidation, or out-of-swing prices return `BLOCK_INVALID_GEOMETRY`; uncertainty never allows entry.

A future approved APC integration may consume `entry_permission`: false prevents start/scale; `WAIT_*` retains budget without deployment; allowed permits APC construction evaluation. This Phase 1 does not perform that integration. Known limitations: swing/impulse/support/resistance are supplied geometry rather than derived from market data, and thresholds are conservative static defaults pending approved calibration.
