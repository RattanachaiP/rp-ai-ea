# PR262 V28 Decision Intelligence

## Architecture

Decision Intelligence consumes the seven immutable PR261 contexts and never consumes
bars, ticks, prices, or indicators. `expectancy_engine` validates an opportunity's
explicit historical edge record; `risk_eligibility` decides whether accepting risk is
justified; `confidence_engine` describes agreement, consistency, maturity, reliability,
and quality; and `decision_engine` applies the final all-gates rule. Risk cannot create
or rescue expectancy.

The layer is deterministic and pure. It has no clock, filesystem, network, learning,
configuration mutation, publisher, Executor, or broker dependency.

## DecisionContext schema

`DecisionContext` is an immutable `V28.DECISION_CONTEXT.1.0` value containing decision,
direction, expectancy, confidence, risk eligibility, human reason, supporting evidence,
conflicting/rejected evidence, context and evidence lineage, policy references, policy
version, and a SHA-256 replay identity over its canonical decision payload.

BUY or SELL requires positive expectancy, `RISK_ELIGIBLE`, confidence of at least 0.75,
an explicitly executable opportunity, valid evidence quality, and an unambiguous market
side. Every other combination is HOLD/NONE.

## Replay validation

Identical immutable contexts produce the same domain-separated SHA-256 replay identity.
Context evidence identifiers, historical edge identifiers, and both policy versions are
retained in lineage. Mutation attempts fail.

## Examples and runtime log representation

The unit suite constructs all outcomes solely from context contracts:

```text
DECISION_INTELLIGENCE decision=BUY direction=BUY expectancy=POSITIVE_EXPECTANCY risk=RISK_ELIGIBLE confidence=0.983333 executable=true
DECISION_INTELLIGENCE decision=SELL direction=SELL expectancy=POSITIVE_EXPECTANCY risk=RISK_ELIGIBLE confidence=0.983333 executable=true
DECISION_INTELLIGENCE decision=HOLD direction=NONE expectancy=EXPECTANCY_NOT_ESTABLISHED risk=RISK_REJECTED confidence=0.833333 executable=true
```

These are deterministic diagnostic representations, not production publication or broker
logs. PR262 deliberately introduces no runtime side effect.
