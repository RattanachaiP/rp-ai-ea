# PR235 Decision Pipeline

The runtime observer timestamps the completed transitions `Market State ->
Validation -> Decision Context -> Analysis -> Risk Construction -> Decision
Classification -> Decision Publication` in `decision_pipeline_trace.log`.

The observer has no strategy authority. It receives completed stage facts from
the existing V27 runtime and cannot create, repair, cache, or select a market
publication. A rejected cycle records exactly one canonical owner.

