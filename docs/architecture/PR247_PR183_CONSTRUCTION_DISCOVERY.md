# PR247 — PR183 Decision Context Construction Discovery

## Architecture analysis and finding

The repository is in case **A**. The PR183 lifecycle already has its sole owner,
`GovernedDecisionContextEngine.construct_context()`, and its atomic append-only
`DecisionContextRepository`. The engine accepts only canonical PR182 confidence
records, reports, or snapshots and verifies source membership, integrity, repository,
snapshot, policy, and engine partitions before persistence. Its focused tests already
cover deterministic replay, collision rejection, canonical encoding, provenance, and
repository-chain integrity.

What did not exist was an operator or bootstrap composition for PR183. Production
startup begins later from an explicitly activated PR184 bundle, and PR184 construction
requires an already-persisted PR183 snapshot. Consequently, a new installation with no
`learning_data` tree correctly failed at PR184: no governed command existed to supply
an exact PR182 snapshot to the existing PR183 owner. The missing directory was an
uninitialized append-only repository, not permission to create JSON or identities by
hand.

## Authoritative lifecycle

```text
PR182 owner produces canonical Confidence records and snapshot
  -> operator supplies one exact PR182 snapshot UUID
  -> operator_construction loads the canonical PR182 repository
  -> exact snapshot match and repository verification (fail closed)
  -> GovernedDecisionContextEngine.construct_context(snapshot)
  -> DecisionContextRepository atomically appends deterministic records/snapshot
  -> separate PR184 operator construction may consume that exact PR183 snapshot
```

There is no latest-record selection, UUID generation in the CLI, manual JSON, PR184
activation, inspection mutation, Runtime invocation, Strategy change, or Executor
change in this lifecycle.

## Operator command

```bash
python -m learning.decision_context.operator_construction \
  --confidence-snapshot-uuid <exact-pr182-snapshot-uuid>
```

The optional `--confidence-repository-root` and `--repository-root` arguments support
controlled deployments and tests. `--format json` prints the owner engine's canonical
report; it does not use printed JSON as repository input. Missing, corrupt, ambiguous,
or unmatched PR182 source state fails before the PR183 target is initialized. Repeating
the exact command returns the deterministic canonical identities without changing any
persisted bytes.

## Ownership inventory

- **Decision Context owner/API:** `GovernedDecisionContextEngine.construct_context()`.
- **Decision Context repository:** `DecisionContextRepository`, which exclusively owns
  atomic record and snapshot persistence under `learning_data/decision_context`.
- **Construction CLI:** `learning.decision_context.operator_construction`, limited to
  exact-source lookup and composition through the two owners above.
- **Upstream owner:** PR182 `RuntimeConfidenceRepository`; the CLI reads one exact
  canonical snapshot and never alters PR182.
- **Downstream construction:** PR184
  `learning.decision_intelligence.operator_construction`, which remains separate.
- **Bootstrap/production:** PR184 bootstrap rejects implicit activation; production
  startup consumes an explicit owner-governed PR184 activation and owns no PR183
  construction.
- **Tests:** PR183 engine/repository behavior remains covered by
  `test_pr183_decision_context.py`; PR247 CLI composition and failure boundaries are
  covered by `test_pr247_operator_construction.py`.
