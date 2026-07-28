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

## Completed-trade event boundary

The production host invokes `MT5CompletedTradeEventProducer.emit_after_completion`
only after MT5 has reported the closing deal, the broker-confirmed final values
are available, and the position lifecycle is complete. The producer passes the
host facts unchanged into the PR203 canonical contract. Its publisher rejects a
second emission for the same replay identity and broker tickets before notifying
the existing passive operational-evidence subscribers.

## V27.2 Interactive Editor

V27.2 expands the chart panel from a profile loader into a post-entry interactive editor. The panel keeps the AI boundary intact: it does not expose direction, bias, signal, entry timing, market classification, or AI decision controls.

Runtime controls are displayed in three columns and can be adjusted with on-chart `+` / `-` buttons, then applied immediately with **Apply Runtime**. **Save JSON** persists the current in-memory profile to `trade_management_dashboard.json` and `dashboard_profiles/<ActiveProfile>.json`; **Reload JSON** reloads the active JSON profile without recompiling.

Visible sections include Profile, Risk, Breakeven, Trailing, Profit Lock, Runner, Time Exit, Partial Close, status telemetry, active exit authority owner, effective management mode, and open-position ticket/profit/protection rows.

## Canonical governed executor (PR237)

`canonical/RP_AI_Governed_Executor.mq5` is the sole consumer of the canonical
`execution_package.json` boundary. It does not read `decision.json`, construct
packages, calculate confidence, size lots, or run strategy gates. A package is
accepted only when its canonical Runtime producer/version/schema capability,
identity, lineage, freshness, sequence, and complete order facts validate.

Before `OrderSend`, the executor validates symbol availability, terminal and
symbol trading permission, a fresh broker tick (market open), broker volume
constraints, free margin, and stop distances. It durably appends the accepted
`execution_uuid` before submission and also persists the latest acceptance in
`executor_state.json`; package deletion or a non-adjacent replay therefore
cannot authorize the UUID again. Every terminal outcome is written to
`execution_result.json`, while `executor_trace.log` records the governed stage,
status, failure owner, and reason.
