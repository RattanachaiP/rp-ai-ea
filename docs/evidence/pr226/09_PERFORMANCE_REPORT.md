# PR226 Performance Report

**Result: FAIL — no live samples.**

| Statistic | Value |
|---|---|
| Sample count | 0 |
| Average | NOT MEASURED |
| P95 | NOT MEASURED |
| Maximum | NOT MEASURED |

No latency is reported for any canonical hop because no real MT5 Demo execution
occurred.  Repository test duration and PR224 deterministic timestamps are not
broker latency and are not reused.  A certification rerun must preserve raw
monotonic checkpoints from Writer through broker fill and state its clock,
units, inclusion rule, and per-hop as well as end-to-end statistics.

