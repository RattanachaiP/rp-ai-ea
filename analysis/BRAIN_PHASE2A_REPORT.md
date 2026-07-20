# Brain Phase 2A Market Perception report

## Result

**PASS.** Market Perception is now a private, observation-only object. A deterministic V26 candidate decision is exactly equal to the `HEAD` baseline. No `decision.json` file was written.

## Extracted observations

| Observation | Extraction |
| --- | --- |
| Trend | Ordered MA50/MA90/MA200. |
| Swing High / Low | Candle-series extrema. |
| Market Structure | Higher-high/higher-low or lower-high/lower-low candle progression. |
| Liquidity Sweep | Breach and close back through a prior candle extreme. |
| Volatility | Current versus average candle range. |
| ATR State | Raw ATR telemetry availability only. |
| VWAP Relation | Bid above, below, or at supplied VWAP. |
| Session | UTC descriptive session from market timestamp. |
| Momentum Observation | RSI/MACD alignment. |
| Compression / Expansion | BB width and candle-range observation. |
| Impulse Detection | Current candle body-to-range observation. |

## Mapping

`read_market()` dictionary → `brain_market_perception()` → private `MarketPerception` → `brain_market_understanding()` → exact original dictionary → existing `build_decision()` path. The object is not serialized or merged into the candidate decision.

## Runtime impact

The layer does not choose an action, calculate a trade score, or determine BUY/SELL. It has no MT5, dashboard, executor, writer, or `decision.json` dependency. Existing V26 logic receives the original dictionary by object identity after Market Understanding.

## Parity verification

The generator compared complete `build_decision()` dictionaries for a deterministic invalid-bid fixture against `HEAD`; they were equal. It also verified perception-object unwrapping returns the original market-state object and that the object has no decision field.
