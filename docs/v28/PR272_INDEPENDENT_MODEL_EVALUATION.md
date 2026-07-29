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
dataset splits are explicit, and no wall clock, random source, or external state
is read, so identical inputs produce an identical report.

Qualification is evidence only. Reports are advisory and cannot authorize
Runtime, deployment, promotion, or production. Evaluation never retrains or
tunes a model, generates a candidate, changes Runtime, deploys a model, promotes
a model, or approves production.
