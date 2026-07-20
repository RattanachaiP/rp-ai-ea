# RP AI Brain V1 Dependency Graph

**Architecture version:** `V1 Frozen`
**Scope:** Typed, private in-process Brain pipeline only.

```text
caller-owned raw market-state Mapping
                |
                v
  brain.market_perception.extract_market_perception
                |
                v
             MarketPerception
                |
                v
  brain.market_understanding.interpret_market_understanding
                |
                v
            MarketUnderstanding ------------------+
                |                                 |
                v                                 |
  brain.market_reasoning.reason_about_market       |
                |                                 |
                v                                 |
             MarketReasoning ---------------------+
                                                  |
                                                  v
       brain.probability_engine.estimate_market_probabilities
                                                  |
                                                  v
                                   ProbabilityAssessment (private telemetry)

unchanged original Mapping --by identity--> authoritative V26 build_decision()
                                           --> unchanged decision.json writer
```

## Imports and allowed edges

| Consumer module | Allowed Brain imports | Input and output | Coupling finding |
| --- | --- | --- | --- |
| `market_perception` | None | `Mapping[str, Any] -> MarketPerception` | Leaf observation layer; no engine/runtime import. |
| `market_understanding` | `MarketPerception` only | `MarketPerception -> MarketUnderstanding` | One downward dependency. |
| `market_reasoning` | `MarketUnderstanding` only | `MarketUnderstanding -> MarketReasoning` | One downward dependency. |
| `probability_engine` | `MarketUnderstanding`, `MarketReasoning` only | matching pair `-> ProbabilityAssessment` | Terminal analytical layer; validates pair identity. |

The V26 engine is an adapter/consumer, not a dependency of any Brain module. It
creates the private sequence, confirms the probability type, then unwraps the
original mapping before the unchanged `build_decision()` path. The assessment
is neither serialized nor consumed by the writer, MT5, dashboard, executor, or
decision payload.

## Forbidden edges verified

* **Probability -> Perception:** absent. `probability_engine.py` imports only
  Understanding and Reasoning.
* **Reasoning -> Perception mutation:** absent. Reasoning imports Understanding
  only, creates tuples/strings, and has no mutation operation.
* **Understanding -> Probability mutation:** absent. Understanding does not
  import Probability and only returns its own frozen context object.
* **Any typed Brain layer -> V26/MT5/dashboard/executor/writer:** absent.

Static dependency and immutability checks are enforced by
`tests/test_brain_v1_architecture.py`.
