# Production Demo Certification (PR256)

## Authority and boundary

Certification is offline, read-only, advisory-only, and incapable of changing
Runtime, AI, Strategy, Execution, Learning, promotion, or live-trading state.
`READY FOR LIVE REVIEW` authorizes only human review. Human approval remains
mandatory before live trading.

## Governed policy

Every run explicitly selects an immutable
`PR256.PRODUCTION_DEMO_CERTIFICATION_POLICY.1.0` JSON document. It declares
`policy_id`, `policy_version`, `owner`, `approver`, `effective_at_utc`, and
`approved_thresholds`. Each threshold is a typed numeric `value` with a `unit`.
The output records the policy identity, authority, effective time, and SHA-256.

Architecture safety bounds cannot be weakened by policy: the completed-trade
sample is an integer of at least 300, minimum Profit Factor is at least 1.1
ratio, and maximum equity drawdown is no more than 25 percent. Booleans,
strings, NaN, infinity, missing units, and fractional trade samples fail closed.

## Cohort manifest and temporal proof

Every run explicitly selects an immutable
`PR256.CERTIFICATION_EVIDENCE_MANIFEST.1.0`. Its `evidence_batch_id`, observation
window, freshness limit, and exact `(basename, SHA-256)` snapshot set bind one
cohort. Aggregate reports must repeat the batch and exact window, be generated
within the permitted post-window range, and use a policy effective before the
window.

Continuous operation is proven from a window of at least 604,800 seconds,
runtime start/update coverage, and one `runtime_daily_summary.json` for every
UTC date in the window. Dates must be contiguous and daily generation times
must be in-cohort. Any daily restart or exception fails the continuous-window
gate. Cumulative uptime alone is not used as continuity proof.

## Evidence authority and reconciliation

Runtime execution accepted/rejected counts must equal PR253 execution counts.
PR254 lifecycle totals, successful counts, missing-stage counts, and reported
rate are recomputed from its lifecycle records. Missing or contradictory
metrics fail closed.

`trade_statistics.csv` and MT5 `ReportHistory` are immutable,
manifest-bound **provenance-only** inputs. Their hashes must occur in PR253
provenance. PR253 is the sole governed analytics authority for completed-trade
counts and totals; the certification does not imply independent raw-row
validation.

The canonical drawdown metric is `maximum_equity_drawdown_percent`, unit
`percent`, basis `equity_peak_to_trough`. A different metric, unit, or basis
fails closed.

## Objective gates

| Domain | Gate | Acceptance |
|---|---|---|
| Runtime | Continuous seven-day observation window | At least 604,800 seconds, all UTC daily summaries present, no restart or exception gap |
| Pipeline | Lifecycle success | Reconciled success rate at least 99%, nonzero cohort, zero missing stages |
| Execution | Order submission | Reconciled accepted / total submissions at least 99%, nonzero denominator |
| Execution | Duplicate publication | Zero `duplicate_decision_count`; no claim is made that this is lifecycle duplication |
| Operations | Blocking backlog | Zero unresolved Runtime Stability, Pipeline Completeness, Execution Reliability, or Decision Delivery items; all unresolved P0/P1 items also block |
| Trading | Sample | At least the governed sample, never below 300 completed trades |
| Trading | Expectancy | Strictly positive report-currency expectancy per trade |
| Trading | Profit Factor | At least the governed ratio, never below 1.1 |
| Trading | Drawdown | At most the governed equity peak-to-trough percentage, never above 25% |

Backlog statuses are limited to `PENDING_HUMAN_REVIEW`, `IN_PROGRESS`, and
`RESOLVED`. Resolution requires `approved_by`, `verified_by`,
`resolved_at_utc`, `evidence_reference`, and an
`implementation_or_verification_artifact`; a bare `RESOLVED` never passes.

## Results

* **NOT READY** — a Runtime, Pipeline, Execution, or operational gate fails.
* **READY FOR EXTENDED DEMO** — all operational gates pass but a Trading gate
  remains unmet.
* **READY FOR LIVE REVIEW** — every gate passes; human approval is still
  mandatory and no automatic live transition occurs.

Invalid, stale, mixed, incomplete, inconsistent, or non-authoritative evidence
fails closed. The sole output is atomically replaced
`production_demo_certification.json`; sources are never modified and no
latest-file discovery occurs.
