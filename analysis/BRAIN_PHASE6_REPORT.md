# Brain Phase 6 Position Intelligence report

## Result

**PASS.** Position Intelligence produces a private immutable shadow assessment. Deterministic V26 `build_decision()` output matches the `HEAD` baseline exactly; no `decision.json` file was written.

## Input mapping

The assessment accepts only one matching lineage: `MarketUnderstanding` provides regime, structure, volatility, context quality, and invalid conditions; `MarketReasoning` provides conflicts; `ProbabilityAssessment` provides non-directional market-state estimates; and `ExpectedValueAssessment` provides normalized risk/reward, expected value, and uncertainty. It accepts no V26 decision dictionary, payload, prices for construction, risk settings, dashboard, MT5, executor, or writer state.

## Position-assessment methodology

All labels are descriptive normalized context. The example is `TREND_CONTEXT` with `CONTEXTUALLY_ELIGIBLE`, `ANALYTICAL_STANDARD`, `STRUCTURE_INVALIDATION_CONTEXT`, `CONTINUATION_OR_EXPANSION_CONTEXT`, and `FAVOURABLE_NORMALIZED_FEASIBILITY`. Position uncertainty is `0.0875` (LOW_UNCERTAINTY). Structure and reasoning conflicts create invalidation context; no exact entry, stop, target, lot, or live risk is fabricated.

## Examples of analytical outputs

Scalp `SUITABLE`; intraday `SUITABLE`; runner `SUITABLE`; scale-in `SUITABLE_IF_CONTEXT_PERSISTS`; partial exit `CONTEXT_DEPENDENT`; position quality `HIGH_CONTEXTUAL_POSITION_QUALITY`. These are not execution recommendations.

## Runtime isolation

**NONE.** The V26 runtime neither imports nor invokes this module. It has no BUY/SELL authority and cannot alter V26 direction, entry, SL/TP, lot size, risk, payload construction, publication, MT5, executor, or dashboard behavior.

## Payload parity

**PASS.** The assessment is neither serialized nor merged into `decision.json`; baseline and candidate complete deterministic V26 payload dictionaries are equal.

## Regression status

**PASS.** Immutability, lineage validation, non-executable analytical output, runtime isolation, and payload parity passed.

## DATA_CONTRACT impact

**Non-breaking extension only.** The frozen production compatibility boundaries and payload schema remain unchanged. The private typed Phase 6 contract adds no published field and transfers no ownership.

## Execution authority

**Unchanged.** V26 remains authoritative for direction, entry, stop loss, take profit, lot size, risk, payload construction, and publication. No execution authority moved.
