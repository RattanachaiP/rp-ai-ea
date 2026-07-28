# PR235 Decision Pipeline

The runtime observer timestamps the completed transitions `Market State ->
Validation -> Decision Context -> Analysis -> Risk Construction -> Decision
Classification -> Decision Publication` in `decision_pipeline_trace.log`.

The observer has no strategy authority. It receives completed stage facts from
the existing V27 runtime and cannot create, repair, cache, or select a market
publication. A rejected cycle records the exact component in `failure_owner`
and one canonical `DecisionBlockReason` in `failure_reason`; the two fields are
never conflated. `failure_detail` contains controlled diagnostic context.

Every NORMAL publication uses the same strict verification path. Missing
producer metadata is owned by `PUBLISHER`, classified `INVALID_SCHEMA`, and
cannot reach runtime promotion. There is no compatibility bypass in activation
authority. Verification failure is written to runtime health and the pipeline
trace before its typed exception propagates.
