# PR238 First Successful Execution

**Status:** **NOT CAPTURED**

No authentic `market_state.json`, connected MT5 terminal, Demo account session, `OrderSend` result, order ticket, or `execution_result.json` was available on the collection host. Consequently there is no first successful execution to report, and the acceptance statements `END_TO_END_PIPELINE = VERIFIED` and `FIRST_DEMO_EXECUTION = SUCCESS` are **not claimed**.

## Required rerun evidence

1. Preserve the fresh writer publication and its sequence/source UUID.
2. Preserve the decision and execution package with matching lineage.
3. Preserve executor trace and journal entries through `SUBMITTING` and `SUBMITTED`.
4. Preserve the authentic broker retcode/ticket and atomically written result.
5. Calculate hop latency from those raw timestamps and confirm the execution UUID occurs exactly once.
