# PR272 Independent Model Evaluation Foundation

`learning.evaluation` is an offline, independent authority that evaluates an
already-registered PR271 candidate against authoritative PR269 learning evidence
and its PR270 analytics report. It does not import or invoke the Training
Foundation. All evaluation inputs are reconstructed and lineage-bound before
any score is calculated.

The report covers predictive performance, generalization, stability,
calibration, risk characteristics, replay consistency, dataset coverage,
confidence reliability, and regime robustness. It includes descriptive
statistics, an aggregate candidate score, explicit qualification evidence, and
content-addressed input, replay, report, and registry identities. Policies and
dataset boundaries are explicit, and no wall clock, random source, or external
state is read, so identical inputs produce an identical report. Evaluation rows
have immutable identities and an evaluation dataset carries its own content and
version identities plus a proof that its source examples do not overlap the
candidate's ordered training rows. Generalization is calculated only from this
out-of-training dataset; training metrics are never reused as holdout evidence.
The evaluator also reconstructs the evaluation-side Learning Registry, Learning
Evidence, and Outcome Analytics inputs, verifies analytics replay, requires the
evidence to occur exactly once in that registry, and binds every source identity
and ordered example in the evaluation dataset to those authorities. A dataset
whose internal identities merely agree with one another is not authoritative.

The full evaluation policy is content-addressed into every report and replay
computation. Governance requires at least 30 independent records and at least
five records per observed regime by default. Confidence reliability has one
precise meaning: the Brier score between each immutable pre-outcome confidence
and the observed binary profitable/non-profitable result. Qualification and
dimension pass states are reconstructed from those policy thresholds rather
than accepted from callers. The ordered registry links every entry and registry
snapshot to its predecessor and defines uniqueness by candidate, evaluation
dataset, and policy identities.

Qualification is evidence only. Reports are advisory and cannot authorize
Runtime, deployment, promotion, or production. Evaluation never retrains or
tunes a model, generates a candidate, changes Runtime, deploys a model, promotes
a model, or approves production.

The existing V27 Production Executor remains the sole production execution
authority.
