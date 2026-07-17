# Zero-Broker-SL Validation

`ZERO_BROKER_SL_VALIDATION` is a **comparison-only**, isolated-demo/replay profile. It changes only the Broker Stop Loss: the broker SL is disabled (`0.0`), while the fixed +$1.00 TP and the $1.20 hard-loss-cap emergency exit remain active. The previous comparison profile is `Profile_F_MARKET_CLOSE_ONLY` with its 120-point Broker SL.

## Run

Provide separate, closed-trade CSV exports for the previous Broker-SL profile and the new zero-Broker-SL profile. Each needs a numeric realized P/L column (`net_profit`, `profit`, `profit_usd`, `realized_profit`, or `pnl`). Exit source columns are used to rank capital damage.

```bash
python analysis/zero_broker_sl_validation.py \
  --baseline-trades path/to/profile_f_broker_sl_closed_trades.csv \
  --zero-broker-sl-trades path/to/zero_broker_sl_closed_trades.csv \
  --output analysis/zero_broker_sl_validation_report.json
```

The report contains the mandatory comparisons for both replays: Profit Factor, Expectancy, Net Profit, Win Rate, Average Win, Average Loss, Maximum Drawdown, Capital Damage Ranking, and Equity Curve. It also validates a deterministic isolated-demo payload to prove that the active V28 contract has `broker_sl_required=false` and `stop_loss=0.0`; it does not mistake that contract check for a financial outcome.

## Decision rule

Expectancy must be **strictly higher** under the zero-Broker-SL replay. If it is equal or lower, the report returns `NOT_ROOT_CAUSE` and instructs that no further work focus on Broker SL. If either replay lacks closed realized P/L, the result is `UNDETERMINED`; collect matched evidence rather than asserting an outcome.
