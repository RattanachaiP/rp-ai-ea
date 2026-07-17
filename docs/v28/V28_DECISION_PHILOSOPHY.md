# V28 Decision Philosophy: Expectancy Before Direction

## Status and approval gate

**Status: proposal only — implementation is prohibited pending explicit approval.**

V28 does not repair, extend, tune, wrap, or otherwise inherit V27's decision
philosophy. This document is the required design deliverable for a full
thinking-model replacement. It establishes the decision model to review before
any V28 runtime, executor, dashboard, payload, launch, or configuration change
is made.

V27 remains the production runtime and its current operational safeguards remain
unchanged while this proposal is awaiting approval. This proposal does not
authorize filters, cooldowns, waiting states, score adjustments, patch stacks,
or new runtime layers.

The mandatory edge-verification, traceability, self-correction, and new-rule
requirements that extend this philosophy are defined in
`V28_EXPECTANCY_FIRST_ARCHITECTURE_ADDENDUM.md`. Approval of V28 must include
that addendum.

## 1. V28 decision philosophy

Every decision begins with exactly one question:

> **Does this opportunity have positive expectancy?**

The system must answer that question before it considers `BUY` or `SELL`.
Direction is therefore an attribute of a verified opportunity, not the premise
of the decision. An actionable decision is the intersection of a defined
market opportunity, evidence that its expected value is positive after costs,
and a risk package whose downside preserves that positive expectation.

The governing sequence is:

`Market -> Opportunity -> Positive Edge Verification -> Decision -> Risk -> Publish`

`NO_TRADE` is the normal result when positive expectancy cannot be established.
It is not a delayed directional signal, a downgraded trade, or a collection of
secondary vetoes.

## 2. Opportunity definition

An **opportunity** is a testable market situation with all of the following
properties:

1. **A specified setup:** the observed market state identifies a repeatable
   condition rather than merely an indicator preference.
2. **A defined hypothesis:** it states what price behavior is expected, the
   condition that invalidates that expectation, and the time/market context in
   which the hypothesis applies.
3. **A candidate direction:** `BUY` or `SELL` is selected only as the direction
   in which the hypothesis would realize its edge.
4. **Observable payoff boundaries:** entry, invalidation, target/exit behavior,
   estimated costs, and maximum loss are knowable before publication.
5. **Comparable evidence:** the setup can be matched to closed-trade evidence
   from the same opportunity definition so its outcomes are measurable.

An indicator reading, score, bias, candle, or direction by itself is not an
opportunity. Those are observations that may describe one.

## 3. Positive edge definition

A candidate has a **positive edge** only when evidence for its defined
opportunity supports positive net expectancy after trading costs and the
proposed risk construction:

`E_net = P(win) × AvgWin − P(loss) × AvgLoss − ExpectedCosts > 0`

Where `AvgWin`, `AvgLoss`, and `ExpectedCosts` are expressed on a common basis
(currency or R), and the measurement population is the same opportunity type,
direction, and risk/exit construction. The model must also establish that the
loss boundary is known before entry; an unbounded or unknown downside cannot be
classified as positive expectancy.

Positive edge verification must produce a reviewable evidence record containing:

- the opportunity identifier and hypothesis;
- the candidate direction, entry context, invalidation, and planned payoff;
- the evidence sample, measurement period, and net-expectancy calculation;
- cost assumptions and the risk boundary used in the calculation; and
- a result of `POSITIVE_EDGE` or `EDGE_NOT_ESTABLISHED`.

The evidence record must also explicitly estimate expected win probability,
expected average win, expected average loss, expected net expectancy,
historical sample size, and statistical confidence. The mandatory addendum
defines the traceability contract and the evidence requirements for future
decision-logic changes.

The absence of sufficient comparable evidence is `EDGE_NOT_ESTABLISHED`, not a
reason to invent confidence, lower a threshold, wait for a different signal, or
alter a score.

## 4. Decision flow

1. **Market:** collect the current market state and verify only data and
   execution safety required to make a valid observation.
2. **Opportunity:** identify whether the state matches a named, testable
   opportunity and construct its hypothesis and payoff boundaries.
3. **Positive Edge Verification:** measure the opportunity against comparable
   evidence, include costs and planned loss, and determine whether `E_net > 0`.
4. **Decision:** only after a positive edge is verified, choose the candidate
   direction and publish `TRADE`; otherwise publish `NO_TRADE` with
   `EDGE_NOT_ESTABLISHED` or the specific evidence reason.
5. **Risk:** attach the bounded initial risk package that was used to establish
   net expectancy. Risk may not retrospectively create or rescue an edge.
6. **Publish:** publish one auditable decision and its evidence record. The
   executor retains broker and payload safety authority only; it does not
   reinterpret the opportunity or direction.

## 5. Why this replaces V27's failure mode

V27's documented path starts from a directional action/bias and then passes it
through accumulated quality, timing, confidence, validation, and emergency
governance layers. Its history also records finite waits, score-gap rules,
adaptive sizing, entry-location controls, and emergency expectancy patches.
That sequence can decide `BUY`/`SELL` before it has demonstrated that the
particular trade has positive net expectancy; later layers can only suppress,
resize, delay, or manage an already direction-first idea.

V28 removes that premise. It makes opportunity-level net expectancy the sole
decision predicate, uses direction only after that predicate passes, and binds
the risk package to the same expected-value claim. Consequently, it eliminates
these V27 philosophical failures rather than masking them:

- **Direction-first trading:** no action is considered executable merely
  because a bias or score favors one side.
- **Patch-driven participation:** an unproven candidate cannot become valid via
  a cooldown, wait release, score change, confidence tier, or emergency patch.
- **Disconnected risk:** a stop, target, or management profile cannot be added
  after the fact to make an unmeasured directional signal appear profitable.
- **Unauditable rejection/approval:** every decision is tied to a named
  opportunity and an explicit net-expectancy record, so losses can challenge
  the underlying hypothesis rather than trigger another local filter.

This is a philosophy replacement, not a claim that positive expectancy has
already been proven. Proof requires the approved measurement plan and sufficient
closed-trade evidence for each opportunity.

## 6. Approval required before implementation

Approval must explicitly accept all five sections above and
`V28_EXPECTANCY_FIRST_ARCHITECTURE_ADDENDUM.md`: the philosophy, opportunity
definition, positive-edge definition, decision flow, failure analysis, and
mandatory edge-verification, traceability, self-correction, and rule-governance
contracts. Only then may a separate implementation plan be proposed. That plan
must preserve the prohibition on incremental V27 fixes and must not introduce
the disallowed mechanisms unless separately and explicitly approved.
