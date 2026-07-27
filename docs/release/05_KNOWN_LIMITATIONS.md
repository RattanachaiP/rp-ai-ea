# Known Limitations and Blockers

## Release-blocking limitation

| Limitation | Status | Consequence | Closure evidence |
|---|---|---|---|
| Demo Operational Certification | **NOT COMPLETE** | Production Release is **BLOCKED**. No Live-readiness or production-certification claim is permitted. | PR228 real MT5 Demo evidence satisfying every Gate D check and all required approvals. |

The missing evidence includes verified MT5 Demo identity, correlated broker
responses, real `OrderSend` results, complete accepted-order lifecycle,
controlled restart recovery, and evaluated latency measurements. Repository or
architecture review cannot substitute for this evidence.

## Framework limitations

- PR227 defines governance and performs no runtime execution.
- A governed runtime baseline is not proof of broker-facing operational safety.
- Release-candidate planning is not authorization to deploy or trade.
- No final version is tagged and no production release is published by PR227.
- Evidence is valid only for the exact candidate commit, artifacts,
  configuration, terminal/broker context, and acceptance thresholds recorded.
- A PASS from an earlier baseline must be revalidated when a relevant digest,
  configuration, dependency, or operational environment changes.

## Required next action

PR228 must collect and independently review the real Demo execution evidence.
Until that work satisfies Gate D, the only valid release decision is
**NOT APPROVED**, and Production Release remains **BLOCKED**.
