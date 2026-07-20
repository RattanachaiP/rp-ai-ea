# Brain Phase 4 Probability Engine report

## Result

**PASS.** The Probability Engine creates a private immutable market-state assessment while the deterministic V26 decision payload remains exactly equal to the `HEAD` baseline. No `decision.json` file was written.

## Context consumed

The engine accepts only `MarketUnderstanding` and its matching `MarketReasoning`. It uses regime, trend/structure, momentum, expansion/compression, transition, liquidity, context quality, and the reasoning uncertainty record. It does not accept a decision dictionary, V26 confidence, score, risk payload, MT5 data source, dashboard profile, or executor state.

## Probability methodology

The engine starts continuation, reversal, range, breakout, and no-trade at equal prior weight. It applies transparent additive adjustments from Brain context, clips weights at zero, and normalizes them into a distribution that sums to 1. Each state estimate includes supporting evidence, conflicting evidence, one bounded uncertainty estimate, and uncertainty evidence. The output contains no BUY or SELL probability.

Context fixture distribution: continuation `0.5000`, reversal `0.1250`, range `0.1250`, breakout `0.1250`, no-trade `0.1250`.

## Runtime impact

The runtime constructs `ProbabilityAssessment` after the private Market Reasoning object and verifies its type. The assessment is retained only in process, then the unchanged original market dictionary reaches `build_decision()`. The legacy `brain_probability_engine()` remains an identity boundary for the V26 decision dictionary. The engine cannot generate BUY/SELL, replace confidence or scores, filter trades, construct risk, or affect publication.

## Payload parity

**PASS.** The assessment is not serialized, merged into the decision, passed to the decision writer, or consumed by MT5, dashboard, or executor code. Baseline and candidate complete deterministic `build_decision()` dictionaries are equal.

## Regression status

**PASS.** Immutable assessment, required evidence, bounded uncertainty, normalized market-state probabilities, no direction-specific probabilities, and V26 payload parity passed.
