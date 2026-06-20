# MT5 V27.1 Trade Management Dashboard

`RP_AI_TradeManagementDashboard_V27_1.mq5` is an on-chart MT5 Expert Advisor for post-entry trade management only.
It intentionally exposes no controls for AI direction, bias, entry timing, signal generation, or market classification.

## Runtime JSON files

The EA reads and writes files in the MT5 Common Files area so values can be reloaded without recompiling:

- `trade_management_dashboard.json`
- `dashboard_profiles/<active_profile>.json`

If either file is missing or malformed enough that a value cannot be found, the EA keeps embedded V26.6-compatible defaults and marks fallback usage on the chart.

## Controls

- **Save Profile JSON** writes the current runtime trade-management values to the dashboard JSON and active profile JSON.
- **Load/Reload JSON** reloads the dashboard/profile JSON immediately without recompiling.
- **Enable/Disable TM** toggles post-entry management only.

## Executor behavior

When `InpManageOpenTrades=true`, the EA consumes the loaded runtime values for hard-loss close, breakeven SL movement, and trailing SL movement on open positions for the attached symbol.
