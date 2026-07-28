# PR248 End-to-End Governed Learning Bootstrap

## Audit conclusion and true genesis

PR250 now supplies canonical validation, append-only raw retention, and explicit exact-UUID PR173 owner construction. Separately human-approved PR175 envelope admission remains pending PR251, so a fresh clone still cannot fabricate or automatically complete genesis.

A fresh clone contains code, not canonical learning evidence. The first learning
artifact is a PR173 `KnowledgeOutcomeAttributionReport`, created by the
`KnowledgeOutcomeAttributionEngine.analyze()` owner operation from operator-supplied
immutable outcome rows. Those rows are externally acquired historical/live completed
outcomes; they are not produced from another `learning_data` repository. PR175 also
requires a separately approved, integrity-bound `ApprovedPatternMiningEvidenceEnvelope`.
The mining engine deliberately refuses to manufacture or approve that envelope.
Consequently an evidence-free clone **cannot** truthfully become production-ready.

Minimum evidence is a non-empty, single-knowledge-identity set of immutable outcome
rows satisfying PR173, enough samples to pass PR174 policy (normally 30), and the
matching explicitly approved PR175 sample envelope. Production acquisition must export
completed governed outcome evidence from its owning operational evidence process,
review it offline, and admit it through PR173/PR175 contracts. Test fixtures are not
production sources.

## Complete dependency and ownership matrix

| Stage | Owner / construction API | Canonical repository | Input / exact dependency | Snapshot | Fresh-clone role |
|---|---|---|---|---|---|
| PR173 | PR250 acquisition -> `KnowledgeOutcomeAttributionEngine.analyze` | `learning_data/outcome_evidence`, `learning_data/outcome_attribution` | exact imported external immutable outcome record | none | operator-imported genesis |
| PR174 | `GovernedLearningPolicyEngine.evaluate` | `learning_data/learning_policy` | exact PR173 report | none | generated |
| PR175 | `PatternMiningEngine.mine` | `learning_data/pattern_mining` | exact PR174 report + separately approved evidence envelope | none | generated after approval boundary |
| PR176 | `PatternMemoryEngine.create` | `learning_data/pattern_memory` | exact PR175 report | yes | generated |
| PR177 | `PatternValidationEngine.validate` | `learning_data/pattern_validation` | exact PR176 artifact/snapshot | yes | generated |
| PR178 | `PatternPromotionEngine.assess` | `learning_data/pattern_promotion` | exact PR177 artifact/snapshot | yes | generated |
| PR179 | `KnowledgeRegistryEngine.record_admission` | `learning_data/knowledge_registry` | exact PR178 artifact/snapshot | yes | generated |
| PR180 | `RuntimeKnowledgeGate.prepare_advisory_package` | `learning_data/runtime_knowledge` | exact PR179 snapshot | yes | generated; PR248 construct |
| PR181 | `RuntimeKnowledgeSelector.evaluate_eligibility` | `learning_data/runtime_selection` | exact PR180 snapshot | yes | generated; PR248 construct |
| PR182 | `RuntimeConfidenceEvaluator.evaluate_confidence` | `learning_data/runtime_confidence` | exact PR181 snapshot | yes | generated; PR248 construct |
| PR183 | `GovernedDecisionContextEngine.construct_context` | `learning_data/decision_context` | exact PR182 snapshot | yes | generated; PR248 construct |
| PR184 | `GovernedDecisionIntelligenceEngine.construct_intelligence` | `learning_data/decision_intelligence` | exact PR183 snapshot | yes | generated; PR248 construct and separate activation |

PR250 supplies PR173 production ingestion composition; PR175 approval/envelope
admission remains intentionally external and pending PR251. PR180 and
PR182 lacked operator compositions; PR248 supplies them together with PR181, PR183,
and PR184 orchestration. PR184 activation, PR185 onward, and production initialization
remain separate owner workflows.

## Operator modes

All examples below are executable PowerShell syntax. `inspect`, `plan`, and `verify`
are read-only and never choose an identity for mutation:

```powershell
python -m learning.bootstrap.operator_bootstrap inspect --json
python -m learning.bootstrap.operator_bootstrap plan --json
python -m learning.bootstrap.operator_bootstrap verify --json
```

Copy a real snapshot UUID displayed by inspection into a variable. The quoted value
below describes the required value and must be replaced with the real UUID printed by
inspection (it is not an angle-bracket placeholder):

```powershell
$SnapshotUuid = "real-uuid-returned-by-inspection"
python -m learning.bootstrap.operator_bootstrap construct `
  --stage pr182 `
  --source-snapshot-uuid $SnapshotUuid
```

`construct` mutates only the named downstream canonical repository, through its owner
engine. Repeat in lifecycle order for `pr180`, `pr181`, `pr182`, `pr183`, and `pr184`,
each time using the exact result snapshot UUID from the preceding command. A stopped
run is resumed by inspection and an explicit exact-identity rerun; deterministic owner
identities make that rerun idempotent and append-only. The result contains every
constructed record UUID, the exact owner-report snapshot UUID/digest, new record and
snapshot UUIDs, and a distinct `duplicate_replay` flag. It never derives a result from
repository iteration order. For a multi-record PR179 snapshot, PR180 consumes that
snapshot once and its one owner report binds all selected records and the complete
source snapshot identity.

`verify` is also read-only. It verifies the full learning repository chain, PR184
canonical integrity and exact pairs, activation repository integrity, unique owner
activation resolution, and the non-broker production-startup configuration boundary.
It reports `ACTIVATION_REQUIRED` and proves startup is blocked when learning is ready
but activation is absent; after a valid explicit activation it reports the exact
activated pair. Full prerequisite verification additionally requires an operator-supplied
canonical JSON environment-observation file and its exact capture timestamp:

```powershell
$ObservationFile = ".\governed-environment-observations.json"
$CapturedAt = "2026-07-28T12:00:00Z"
python -m learning.bootstrap.operator_bootstrap verify --json `
  --environment-observations-file $ObservationFile `
  --captured-at $CapturedAt
```

The command validates but never persists or invents these external observations. It
then reports production-startup prerequisites ready. It does not start Runtime
or invoke Strategy, Risk, Writer, Executor, broker, or `OrderSend` behavior.

## Production readiness checklist

1. Acquire real governed outcome evidence; run the separate PR173–PR179 owner workflow.
2. Inspect and explicitly construct PR180 through PR184 in order.
3. Run PR184 read-only inspection: `python -m learning.decision_intelligence.operator_inspection inspect --json`.
4. Human-review one exact eligible pair. Do not treat eligibility as approval.
5. Execute the separately printed owner activation command with exact intelligence and
   snapshot UUIDs and an explicit UTC approval timestamp.
6. Run `python -m learning.bootstrap.operator_bootstrap verify --json`.
7. Run `python -m runtime.production_execution_initialization` with its required exact
   environment observations. Startup remains fail-closed before activation.

No bootstrap mode approves, activates, invokes Runtime, communicates with a broker, or
changes Strategy, Risk, Writer, Executor, `OrderSend`, positions, or exits.

## Failure and recovery matrix

| Diagnostic | Meaning / next action | Mutation | Rerun |
|---|---|---|---|
| `BOOTSTRAP_GENESIS_SOURCE_MISSING` | acquire governed PR173/PR175 external evidence | none | safe |
| `UPSTREAM_SNAPSHOT_REQUIRED` | inspect the named upstream stage and pass one real exact UUID | none | safe |
| `AMBIGUOUS_UPSTREAM_SNAPSHOT` | repair/audit duplicate identity corruption | none | safe after repair |
| `PROVENANCE_VERIFICATION_FAILED` | audit the named corrupt repository; do not bypass it | none | safe after repair |
| `NO_APPROVED_DECISION_INTELLIGENCE` | perform human PR184 review | none | safe |
| `ACTIVATION_REQUIRED` | run explicit PR184 owner activation | none by bootstrap | safe |
| `PRODUCTION_NOT_READY` | complete approval, activation, environment, and startup gates | none by verification | safe |
