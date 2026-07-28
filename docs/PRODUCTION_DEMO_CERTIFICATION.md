# Production Demo Certification (PR256)

## Scope and authority

Certification is an offline, read-only evaluation. It cannot change the
Runtime, AI, execution, strategy, risk, learning, promotion, or live-trading
state. A `READY FOR LIVE REVIEW` result is advisory and **never authorizes live
trading**; human approval remains mandatory.

## Authoritative evidence

The certifier accepts only `runtime_metrics.json`,
`runtime_daily_summary.json`, `production_trading_report.json`,
`pipeline_validation_report.json`, `production_improvement_backlog.json`,
`trade_statistics.csv`, and one or more MT5 `ReportHistory` exports. The
production report's SHA-256 provenance must match every selected raw runtime
and trade snapshot. Every selected input digest is recorded in the result.

## Objective gates

| Domain | Gate | Acceptance |
|---|---|---|
| Runtime | Continuous operation | At least 604,800 seconds (7 days) |
| Runtime | Unexplained crash | Zero recorded restarts and runtime exceptions |
| Pipeline | Interruption | Zero missing lifecycle stages |
| Pipeline | Success rate | At least 99%, with at least one lifecycle |
| Execution | Order submission | Accepted / (accepted + rejected) at least 99%, with at least one submission |
| Execution | Unresolved failures | Zero non-resolved execution-reliability backlog items |
| Execution | Duplicate lifecycle | Zero duplicate decision/lifecycle observations |
| Trading | Sample | At least 300 completed trades, or a higher human-selected statistically required sample |
| Trading | Expectancy | Strictly positive |
| Trading | Profit Factor | At least the human-supplied team acceptance threshold |
| Trading | Maximum drawdown | At most the human-supplied approved risk limit |

The sample requirement cannot be configured below 300. Profit Factor and
drawdown limits have no embedded strategy defaults: the team must supply its
approved values for every certification run.

## Result policy

* **NOT READY** — any Runtime, Pipeline, or Execution gate fails. Operational
  integrity failures cannot be overridden by trading performance.
* **READY FOR EXTENDED DEMO** — every operational gate passes, but one or more
  Trading gates has not yet passed. More demo evidence or human review is
  required; this is not live readiness.
* **READY FOR LIVE REVIEW** — every gate passes. This permits only mandatory
  human review, not a transition to live trading.

Invalid, missing, mismatched, non-finite, or non-authoritative evidence fails
closed without producing a new certification report.
