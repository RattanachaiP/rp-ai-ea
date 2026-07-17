# V28 Expectancy-First Decision Philosophy — Architecture Addendum

## Status

**Mandatory design extension.** This addendum extends
`V28_DECISION_PHILOSOPHY.md` and is binding on the V28 design review. It is
architecture only: it authorizes no production behavior, runtime, executor,
dashboard, payload, or configuration change. The existing V28 approval gate
remains in force.

## Mandatory edge-verification contract

Positive edge must not be established by indicator agreement, score agreement,
filter agreement, or momentum agreement alone. Those observations may describe
an opportunity, but they are not evidence that it has a positive edge.

An approved opportunity must be supported by historically verified positive
expectancy. Its evidence record must explicitly estimate, on a common monetary
or R-multiple basis and after expected trading costs:

- expected win probability;
- expected average win;
- expected average loss;
- expected net expectancy;
- historical sample size; and
- statistical confidence.

The record must identify the comparable historical population, measurement
period, opportunity type, candidate direction, and the risk/exit construction
used for the estimate. If any estimate cannot be reasonably justified,
including because comparable evidence is insufficient or confidence is not
adequate for review, the final decision status must be
`EDGE_NOT_ESTABLISHED`.

No trade may be approved without this documented edge-verification record. Risk
construction may bound an approved opportunity's downside, but it may not
create, infer, or rescue an unverified edge.

## Mandatory decision traceability

Every completed trade must preserve its complete decision lineage so that a
loss can be traced to the decision calculation that approved it. The completed
trade record must include, at minimum:

- decision version;
- decision branch;
- market regime;
- opportunity type;
- candidate direction;
- approval rule;
- risk construction; and
- final decision.

The lineage must remain linked to the associated edge-verification evidence,
including the historical sample and expectancy estimate used at approval.

## Mandatory self-correction policy

V28 does not seek to identify isolated losing trades. It seeks to identify the
decision patterns responsible for cumulative capital damage. Before any future
improvement is implemented, its proposal must answer all of the following:

1. Which decision pattern is responsible for the observed losses?
2. Which historical loss group will be reduced?
3. How much cumulative capital damage is expected to be eliminated?

If these questions cannot be answered with traceable historical evidence, the
modification must not be implemented.

## Mandatory rule for new decision logic

No decision rule may be added merely because it appears reasonable. A proposed
rule must specify:

- the exact historical failure pattern it addresses;
- the decision calculation it modifies; and
- the measurable improvement expected.

Rules without measurable objectives must be rejected. This requirement applies
equally to decision, risk, and management logic; it cannot be bypassed through
an emergency patch or a configuration change.

## Architecture principle and success criteria

V28 must improve the quality of decision calculations. It must not add
complexity through additional filters, cooldowns, waiting states, score tuning,
exception handling, or runtime patches. Complexity without measurable
expectancy improvement is prohibited.

Architecture decisions must be evaluated by profit factor, positive expectancy,
net profit, equity slope, capital-damage reduction, and decision traceability.
Trade frequency is not a success metric.

V28 replaces V27's decision philosophy to produce a more profitable decision
engine, not a more complex AI. Every architectural change must demonstrate a
measurable expected improvement in long-term profitability before it can be
implemented.
