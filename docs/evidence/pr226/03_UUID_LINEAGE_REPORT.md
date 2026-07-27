# PR226 UUID Lineage Report

**Result: FAIL — lineage not observed.**

| Link | Required equality | Observation |
|---|---|---|
| MarketState → Context | Context source is exact MarketState UUID | MISSING |
| Context → Intelligence | `context_uuid` is exact Context UUID | MISSING |
| Intelligence → Activation | selected Intelligence UUID is exact | MISSING |
| Activation → Recommendation | recommendation retains selected Intelligence UUID | MISSING |
| Recommendation → Readiness | `recommendation_uuid` is exact | MISSING |
| Readiness → Environment | readiness UUID is exact | MISSING |
| Readiness/Environment → Feasibility | both parent UUIDs are exact | MISSING |
| Feasibility → Package | feasibility and governed parent UUIDs are exact | MISSING |

There is no PR226 run identifier or runtime artifact from which these identities
can be extracted.  Under the stated rules, missing lineage evidence is a
certification failure and cannot be inferred from repository tests.

