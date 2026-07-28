# PR238 Latency Report

**Verdict:** **NO AUTHENTIC SAMPLES AVAILABLE.**

| Segment | Start evidence | End evidence | Sample | Status |
|---|---|---|---:|---|
| Writer → Runtime | Writer publication time | governed reader acceptance | — | NOT OBSERVED |
| Runtime → Decision | runtime acceptance | decision atomic publication | — | NOT OBSERVED |
| Decision → Package | decision publication | package publication trace | — | NOT OBSERVED |
| Package → Executor | package publication | executor validation trace | — | NOT OBSERVED |
| Executor → Broker | `OrderSend` attempted trace | broker return | — | NOT OBSERVED |
| Broker → Result | broker return | result recorded trace | — | NOT OBSERVED |

Repository unit-test timings and deterministic broker doubles are intentionally excluded: they are not measurements of an MT5 Demo broker. Latency certification requires collection from the connected Demo terminal using one execution UUID and a common UTC/monotonic capture timeline.
