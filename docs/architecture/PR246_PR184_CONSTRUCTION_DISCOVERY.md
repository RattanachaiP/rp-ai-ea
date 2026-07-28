# PR246 — PR184 Construction Discovery and Bootstrap Verification

## Finding and root cause

The repository is in case **A**: the PR184 construction lifecycle already exists.
`GovernedDecisionIntelligenceEngine.construct_intelligence()` is the sole construction
owner, and `DecisionIntelligenceRepository` is its atomic, append-only persistence
boundary. The PR184 bootstrap deliberately rejects the retired construct-and-activate
shortcut, while the existing operator commands cover inspection and activation only.
The missing `learning_data/decision_intelligence` directory is therefore an
uninitialized repository, not evidence that the construction engine is absent. The
root cause was the absence of an operator-facing composition that supplied an exact
canonical PR183 snapshot to the existing owner engine.

## Authoritative lifecycle

```text
exact operator-supplied PR183 snapshot UUID
  -> canonical PR183 repository load and exact match (fail closed)
  -> GovernedDecisionIntelligenceEngine.construct_intelligence(snapshot)
  -> DecisionIntelligenceRepository atomic append-only records and snapshot
  -> operator_inspection (read only; no selection)
  -> explicit human approval
  -> operator_activation with exact PR184 record/snapshot UUIDs and UTC timestamp
  -> production_startup resolves the sole activation
```

Construction does not activate its output. Inspection does not construct or activate.
Activation does not infer identities. Production startup does not construct, repair,
select a latest record, or initialize an empty repository.

## Operator construction command

```bash
python -m learning.decision_intelligence.operator_construction \
  --context-snapshot-uuid <exact-pr183-snapshot-uuid>
```

Optional repository-root arguments support controlled deployments and tests. The
command creates no UUID and writes no JSON itself: it loads the exact canonical PR183
snapshot and delegates construction and persistence to the existing PR184 engine and
repository. Missing, corrupt, ambiguous, or unmatched source state fails before the
target repository is initialized. Exact replay returns the deterministic identities
and leaves canonical bytes unchanged.

## Discovery inventory

- CLI entrypoints: `operator_construction`, `operator_inspection`, and
  `operator_activation`; production consumption begins at `runtime.production_startup`.
- Owner engine/API: `GovernedDecisionIntelligenceEngine.construct_intelligence()`
  (also exposed as `run`).
- Repository initialization: lazy and owner-driven through
  `DecisionIntelligenceRepository.save()` and `save_snapshot()`.
- Bootstrap: `GovernedDecisionIntelligenceBootstrap` is an intentional fail-closed
  guard against implicit construction plus activation, not a repository initializer.
- Production composition: `runtime.production_startup` consumes the sole exact
  owner-governed activation and never constructs PR184 state.
- Construction proof: `test_pr184_decision_intelligence.py` proves engine behavior;
  `test_pr246_operator_construction.py` proves exact CLI composition, deterministic
  replay, owner-only persistence, and fail-closed missing-source behavior.
