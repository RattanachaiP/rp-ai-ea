# PR182.1 Independent Implementation Verification

Date: 2026-07-25 (UTC)

Review target: `5b79dcb` against merge base `2f43f94`

Review scope: complete submitted delta plus directly affected canonical PR175–PR182 models

## Baseline and patch

- The checkout has no configured remote or local `codex-dev` ref. The supplied pre-PR
  merge commit `2f43f94ee870ddf8f57f606c78e0f25ace220a64` is therefore the review
  base and merge base.
- The submitted head is `5b79dcbf9232b5bac894412d2d3fac2521a716f9`.
- One commit was reviewed: `5b79dcb PR182.1: Remediate PR181–PR182
  governance provenance & partition integrity`.
- The delta changes nine files with 305 insertions and 34 deletions. Production
  changes are confined to `learning.runtime_selection` and
  `learning.runtime_confidence`; no Runtime, bridge, Executor, broker, risk, or
  decision-publication file changes.

## Claim-to-code verification matrix

| Claim | Implementation and validation path | Identity / failure behavior | Test evidence | Result |
|---|---|---|---|---|
| Additional provenance fields | `RuntimeKnowledgeSelection`, `ConfidenceRecord`; selector/evaluator field propagation | Included by complete dataclass `identity_payload()`; malformed parent reconstruction raises | Exact canonical PR180 and PR181 reconstruction assertions | VERIFIED |
| Validator identity and configuration | `source_validator_version`, `source_validation_policy_version`, `source_validation_config_digest` | Record identity and inherited repository partition | Focused suites plus independent mutation test | VERIFIED |
| Mining identity and policy/configuration | `source_mining_engine_version`, `source_mining_policy_uuid/version`, `source_mining_config_digest` | Alias equality to canonical PR180 mining fields; record/snapshot/report partition | Focused suites plus independent mutation test | VERIFIED |
| Evidence envelope, source and replay propagation | Evidence-envelope UUID/digest, source digest, replay digest copied PR180 -> PR181 -> PR182 | Parent reconstruction and record UUID/digest reject alteration | Canonical reconstruction plus independent mutation test | VERIFIED |
| Package-to-selection reconstruction | `RuntimeKnowledgeSelection.runtime_package_dict()` constructs exact `RuntimeKnowledgePackage` | Canonical package UUID/digest and recursive Registry provenance validation fail closed | `test_selection_retains_complete_policy_partition_lineage_and_evidence` | VERIFIED |
| Selection-to-confidence reconstruction | `ConfidenceRecord.eligibility_record_dict()` constructs exact `RuntimeKnowledgeSelection` | Eligibility UUID/digest and nested PR180 reconstruction fail closed | `test_complete_standalone_provenance_is_retained` | VERIFIED |
| Policy-partition continuity | Expanded PR181 and PR182 `PARTITION_FIELDS`; repository `validate_partition()` uses the complete tuple | Record/report/snapshot identity and mixed-root validation | Existing mixed-partition tests plus independent mutations | VERIFIED |
| Snapshot integrity | Existing snapshot models and repositories consume expanded partition tuples | UUID/digest, predecessor, head, membership, repository digest, source context fail closed | Historical, corrupt-chain, and replay tests | VERIFIED |
| Report integrity and accounting | Existing reports compare complete partitions, source binding, records and counters | Report UUID/digest and `new + duplicate == processed` validation | Focused report/counter tests | VERIFIED |
| Append-only and collision behavior | Existing atomic link-based repositories were not modified by this patch | Existing content cannot be overwritten; changed canonical content collides or fails load | Replay/collision tests and independent identical replay | VERIFIED |
| Deterministic identities | Complete serialized dataclass payloads feed domain-separated identity helpers | Each independently mutated critical field changed UUID | Independent negative verification | VERIFIED |
| Repository preservation | No repository implementation file changed; expanded model partitions are consumed by existing repository logic | Existing append-only behavior preserved | Full governed and regression suites | VERIFIED; PR description's statement that save/load semantics were updated is INCORRECT |
| Documentation synchronization | Current state, flow map, and changelog | Matches verified source and retains PR183 block | Direct source/document comparison | VERIFIED |

## Provenance and parent reconstruction

PR181 now retains every governance field present on the canonical PR180 package.
Its model reconstructs that exact package, including its UUID and digest, which in
turn reconstructs the canonical Registry record and recursively validates the
promotion, validation, memory, mining, evidence-envelope, attribution, source,
and replay lineage. The PR181 engine first resolves the exact package in the
configured canonical PR180 repository and its earliest historical snapshot; it
does not search by partial identity or substitute the repository head.

PR182 first requires exact equality with a stored canonical PR181 record, resolves
the record's earliest historical PR181 snapshot membership, and binds that
snapshot and repository digest. A confidence record then reconstructs the exact
eligibility record, which recursively reconstructs PR180. PR182 imports no PR180
or earlier repository and performs no mutable-state provenance derivation.

## Integrity results

- **Policy partition:** passed. PR181 binds selector, selection policy, Runtime
  packaging, Registry, promotion, validation, and mining dimensions. PR182 adds
  its confidence engine/policy and inherits the complete PR181 partition.
- **Deterministic identity:** passed. Record, report, and snapshot serializers
  include every added field; repository digests remain the ordered canonical
  UUID/digest pairs.
- **Replay/collision:** passed. Identical replay returns stored records, increments
  duplicate counts, preserves repository digest, and reuses the same-context
  snapshot. Altered content cannot overwrite history.
- **Snapshot/report:** passed. Existing unique-head, predecessor, cycle,
  disconnection, membership, partition, source-context, repository-digest, and
  counter checks remain active with the expanded partitions.
- **Authority:** passed. The submitted production diff adds only immutable
  governance fields, reconstruction, and validation. PR181 remains
  `ADVISORY_ELIGIBILITY_ONLY`; PR182 remains `ADVISORY_CONFIDENCE_ONLY`.

## Test-quality findings

The focused tests execute production engines and filesystem repositories without
mocking serializers or partition validation. They cover exact reconstruction,
historical membership, report accounting, replay, collision, mixed partitions,
snapshot corruption, and advisory isolation.

One non-blocking weakness remains: the committed focused tests assert exact
canonical reconstruction but do not parameterize every newly added field to prove
individual identity sensitivity. Independent temporary negative verification
mutated validator version, validation configuration digest, mining engine,
mining configuration digest, evidence-envelope digest, replay digest, selection
policy digest, confidence policy digest, upstream source digest, and historical
snapshot digest; every mutation changed the applicable deterministic UUID.

The removed synthetic insufficient/rejected fixture generated an internally
inconsistent PR181 record by changing embedded upstream states without rebuilding
the canonical PR180 package identity. Rejecting that fixture is correct fail-closed
behavior; it was not valid evidence for a canonical confidence path.

## Findings

### INFORMATIONAL — PR description overstates repository code changes

- **Affected files:** PR description; `learning/runtime_selection/repository.py`;
  `learning/runtime_confidence/repository.py`.
- **Observed:** neither repository file is in the submitted delta.
- **Expected:** claims must distinguish preserved repository semantics from
  modified repository semantics.
- **Reproduction:** inspect `git diff --name-only 2f43f94...5b79dcb`.
- **Impact:** no architecture or behavior defect; existing repository enforcement
  correctly consumes the expanded model partitions.
- **Correction:** describe append-only save/load behavior as preserved, not updated.

### MINOR — per-field mutation coverage is not committed

- **Affected files:** focused PR181/PR182 tests.
- **Observed:** exact reconstruction is asserted, but newly added fields are not
  individually parameterized in committed identity tests.
- **Expected:** critical identity fields should ideally have explicit mutation
  regressions.
- **Reproduction:** inspect the focused test parameter lists; run the temporary
  mutation matrix described above.
- **Impact:** no implementation defect was reproduced; independent verification
  confirmed identity sensitivity.
- **Correction:** optional follow-up test hardening without production changes.

No BLOCKER or MAJOR finding remains. The implementation resolves the four
consolidated-review blockers. PR183 remains unimplemented and blocked until this
remediation is approved and merged.
