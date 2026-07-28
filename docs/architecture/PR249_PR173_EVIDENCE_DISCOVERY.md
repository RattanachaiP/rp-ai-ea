# PR249 PR173 Outcome Evidence Discovery and Governed Acquisition

## Scope and conclusion

This is a repository-wide discovery report, not an acquisition design. It records
only behavior present on `codex-dev`. The audit searched tracked source,
documentation, tests, schemas, workflows, and command entrypoints for the terms in
the PR249 brief, then followed every reference to `learning.outcome_attribution` and
`learning.pattern_mining`.

**Conclusion: a PR173 importer does not exist.** PR173 has an in-memory owner engine,
an immutable output contract, and an append-only report repository. It has no input
row class, input file schema, deserializer, CSV/JSON reader, CLI, importer, exporter,
or adapter from runtime/operational evidence. The missing component is a governed
acquisition/import composition that obtains real completed outcomes, validates and
maps them to the row contract below, establishes their knowledge and replay
identities, and invokes the existing owner engine and repository. That component is
**NOT IMPLEMENTED**.

Consequently a real operator cannot currently feed PR173 through a tracked,
operator-facing production workflow. A Python caller can directly construct a
`list`/`tuple` of mappings (or objects exposing `to_dict()`) and call `analyze()`, but
that low-level API neither acquires nor governs evidence and is not an importer.

## Exact answers: PR173 object model

### 1. Object consumed by `KnowledgeOutcomeAttributionEngine.analyze()`

`analyze(evidence)` consumes a **non-empty Python `list` or `tuple` of rows**. Each
row is either a `dict` or an otherwise unconstrained object with a `to_dict()`
method whose result is a `dict`. There is no named `OutcomeEvidence`, `OutcomeRow`,
`ImmutableOutcome`, `TradeOutcome`, `HistoricalOutcome`, or other PR173 input model.
Those input models are **NOT IMPLEMENTED**.

This matters: `KnowledgeOutcomeAttributionReport` is the output, not the consumed
object. `KnowledgeOutcomeAttributionRepository` stores that output; it does not
store or load source rows.

### 2. Definition

The accepted structural contract exists only in
`learning/outcome_attribution/engine.py`, inside `_validate()`. It is not defined as
a dataclass, JSON Schema, protocol, or standalone schema document. The output
report and its nested output records are frozen dataclasses in
`learning/outcome_attribution/models.py`.

### 3–4. Input schema and fields

The following is a **type/schema description**, not example evidence and not an
import format:

| Field | Presence | Accepted value | Role |
|---|---|---|---|
| `knowledge_uuid` | required, non-empty | value convertible to a UUID | partitions all rows to one knowledge identity |
| `knowledge_version` | required, non-empty | `str` | second half of the knowledge identity |
| `timestamp` | required, non-empty | ISO-8601 string/value accepted by `datetime.fromisoformat`, with timezone | ordering and report `created_at` |
| `replay_digest` | required, non-empty | 64 hexadecimal characters | per-row supplied replay provenance |
| `outcome` | required, non-null | finite `int` or `float`, excluding `bool`; normalized to `float` | observed signed outcome |
| `outcome_metric` | required, non-empty | no PR173 type/allow-list check | outcome contract name |
| `outcome_unit` | required, non-empty | no PR173 type/allow-list check | outcome contract unit |
| `features` | optional | mapping with non-empty string keys and recursively canonical JSON-like finite values | feature contribution and pattern grouping |
| `indicators` | optional | same mapping rules | indicator contribution grouping |
| `risk_factors` | optional | same mapping rules | risk contribution grouping |
| `context` | optional | same mapping rules | context attribution; `regime` also builds regime profiles |
| any other key | optional | not independently validated | retained in the normalized row and therefore in `source_digest`, but otherwise not interpreted |

Allowed nested values in the four named maps are `null`, strings, booleans,
integers, finite floats, lists/tuples, and dictionaries with non-empty string keys.
Unsupported objects, non-finite floats, and invalid map identities fail closed.
There is no exact-field-set constraint and no declared semantics for arbitrary
extra fields.

The output is `KnowledgeOutcomeAttributionReport`, containing:

* `attribution_uuid`, `attribution_version`, `created_at`, `source_digest`,
  `replay_digest`, the sole `knowledge_versions` pair, and `advisory_only`;
* `AnalyticsSummary`;
* feature, indicator, and risk contributions;
* failure and success patterns;
* knowledge performance, market regime, and confidence profiles; and
* context attribution.

### 5. Identity

Input identity is only the common `(knowledge_uuid, knowledge_version)` pair plus
each supplied `replay_digest`. PR173 defines no row UUID. All rows must have exactly
one common knowledge pair; mixed UUIDs or versions fail.

The engine sorts validated rows by parsed timestamp, `knowledge_uuid`, and canonical
row JSON. It hashes that ordered normalized row sequence as `source_digest` and
derives `attribution_uuid` as UUIDv5 in PR173's fixed namespace with
`source_digest` as the UUID name. Identical normalized evidence therefore yields
the same attribution identity independent of input order.

### 6. Digest model

Canonical serialization is compact, key-sorted JSON with non-finite values
forbidden.

* `source_digest = SHA-256(canonical validated-and-sorted full row sequence)`.
* `replay_digest = SHA-256(canonical ordered list of every row's supplied
  replay_digest)`.
* The report has no separate report digest. Its deterministic UUID binds the source
  digest, while the replay digest remains a separate report field.
* The source row replay digest's production algorithm, domain separator, owner,
  and relationship to a replay repository are **NOT IMPLEMENTED/NOT SPECIFIED** by
  PR173.

### 7. Validation

PR173 rejects missing/empty evidence, non-mapping rows, absent or empty required
fields, invalid knowledge UUID, naive/invalid timestamp, invalid replay digest,
non-finite/non-numeric outcome, invalid named maps or nested values, mixed
knowledge identities, and mixed `(outcome_metric, outcome_unit)` pairs. Output
dataclasses additionally validate UUIDs, timezone-aware timestamps, digests,
counts/rates, finite values, the single knowledge pair, and `advisory_only=True`.

Notably absent are a source signature, approver, approval time, source-system ID,
broker/deal/order/position identity, row UUID, duplicate-row rejection, chronology
across trades, future-time check, allowed outcome-contract check at PR173, and a
repository check that raw rows are immutable. These are **NOT IMPLEMENTED** at this
boundary. PR174 later restricts supported outcome contracts.

### 8. Minimum sample count

PR173 requires only one row. Its support/confidence bands are descriptive: below 5
is insufficient, 5–14 low, 15–29 medium, and 30 or more high. PR174's default
governed eligibility minimum is **30**, configurable through
`GovernedLearningPolicyConfig.minimum_pattern_samples`; fewer rows produce
`REQUIRES_MORE_DATA`. PR175 also requires its approved envelope sample count to
equal the PR174 report count. Thus the normal PR173-to-PR175 acquisition needs 30
matching samples, although PR173 alone accepts one.

### 9. Timestamp rules

Every row timestamp must parse as ISO-8601 and include timezone information. `Z` is
accepted by conversion to `+00:00`. Rows are sorted by parsed aware datetime. The
report's `created_at` is the lexicographic maximum of the original timestamp values,
not a newly generated processing time. PR173 does not require UTC specifically,
normalize offsets, require unique timestamps, validate trade chronology, or reject
future timestamps. Those rules are **NOT IMPLEMENTED**.

### 10. Provenance preservation

Provenance is preserved only through content and lineage binding:

1. the complete normalized rows (including arbitrary extra keys) determine
   `source_digest`;
2. the ordered supplied row replay digests determine the report replay digest;
3. the sole knowledge UUID/version and outcome metric/unit are copied into output
   profiles/summary;
4. the report UUID is deterministically tied to source content; and
5. `KnowledgeOutcomeAttributionRepository` writes canonical compact JSON atomically
   to `learning_data/outcome_attribution/report_<attribution_uuid>.json`, accepts
   identical replay, and rejects a same-identity/different-bytes collision.

Raw rows are not persisted by PR173, and there is no source evidence repository or
snapshot identity at this stage. Therefore independently reconstructing or auditing
the raw input from a report alone is impossible. A provenance-preserving acquisition
repository/manifest is part of the missing boundary, not existing architecture.

## Acquisition owner discovery

| Candidate owner | Repository finding for PR173 acquisition |
|---|---|
| Runtime | **NOT IMPLEMENTED.** Runtime has later broker-confirmed live-outcome contracts, but no adapter/import into PR173 and PR173 imports no Runtime code. |
| Backtest | **NOT IMPLEMENTED.** No backtest-to-PR173 producer or acquisition command exists. |
| Replay | **NOT IMPLEMENTED.** Replay-related domains exist elsewhere, but none creates PR173 rows; PR173 merely accepts a supplied digest. |
| Importer | **NOT IMPLEMENTED.** No PR173 CSV/JSON parser, file contract, CLI, or governed importer exists. |
| Manual operator | The architecture says rows are operator supplied, but a tracked operator workflow for supplying them is **NOT IMPLEMENTED**. Direct Python object construction is only a library call. |
| External governance | It is the declared genesis boundary and must provide real evidence, but its acquisition system, owner identity, approval record, and handoff protocol are outside this repository and **NOT SPECIFIED**. |

The later operational chain (`CompletedTradeEvent` -> `LiveOutcomeRecord` ->
operational `OutcomeAttribution`) is a separate PR201/PR203/PR205 lineage with
different contracts and repositories. No code maps it into PR173. Its existence is
evidence that completed-trade facts can be captured by the production host; it is
not evidence of a PR173 importer.

## Importer existence proof

The repository-wide references to `KnowledgeOutcomeAttributionEngine` are its own
package, PR173–PR175 tests, and architecture documentation. Production code has no
caller. The `learning/outcome_attribution` package exports only the engine, error,
output repository, report, and nested output models. It contains no `__main__`,
`argparse`, CSV/JSON load path, or input storage.

CSV readers under `analysis/` perform unrelated offline statistics, autopsy, or
validation. `review_engine.collector.trade_source` belongs to the independent RAIP
review domain. Runtime and operational-evidence outcome files implement post-trade
operational contracts. None imports or invokes PR173. Filename and term searches for
import, history, replay, closed trades, MT5, backtest, JSON, and CSV reveal no
PR173 acquisition composition.

Therefore:

* **CLI:** NOT IMPLEMENTED.
* **Arguments:** NOT IMPLEMENTED.
* **Workflow:** NOT IMPLEMENTED.
* **Canonical import example:** NOT IMPLEMENTED. Supplying one here would invent a
  workflow and is intentionally omitted.

## PR175 approved-evidence boundary

PR175 cannot mine the PR173 report itself because mining requires feature/context
samples, while PR173 outputs aggregates and does not retain its raw rows. The engine
requires both an eligible PR174 `GovernedLearningPolicyReport` and an
`ApprovedPatternMiningEvidenceEnvelope`; absence fails with
`MISSING_APPROVED_PATTERN_EVIDENCE`.

The approval artifact represented in code is the immutable
`ApprovedPatternMiningEvidenceEnvelope` (`PR175.EVIDENCE.1.0`). It contains envelope
UUID/digest; policy UUID/version; source PR173 attribution UUID/source digest/replay
digest; knowledge UUID/version; outcome contract; canonical unique approved samples;
sample count; generation timestamp; and the advisory marker. Each sample has a
sample UUID, feature, market, entry, exit, and risk contexts, finite outcome, and
timezone-aware timestamp.

The envelope digest is SHA-256 over its complete canonical identity payload, and its
UUID is UUIDv5 of that digest in the envelope namespace. Samples sort by UUID;
duplicate identical and duplicate conflicting identities are both rejected. PR175
checks exact policy/attribution/source/replay/knowledge/outcome lineage and exact
sample-count equality before mining. The generated mining report retains the
envelope UUID and digest.

However, `ApprovedPatternMiningEvidenceEnvelope.create()` is a content-addressing
constructor, **not an approval operation**. The envelope has no approver identity,
approval decision, approval timestamp distinct from `generated_at`, signature, or
approval-repository identity. No PR175 approval CLI, approval engine, approval
repository, or mapping from PR173 rows to approved samples exists.

Accordingly:

* **Why approval is required:** the mining owner only accepts an instance of the
  explicitly named approved envelope, exactly bound to the eligible PR174 lineage.
* **How approval occurs:** **NOT IMPLEMENTED** in this repository.
* **Approval artifact:** the envelope is the only represented approved-evidence
  artifact, but evidence of the approval act itself is **NOT IMPLEMENTED**.
* **Approval identity:** **NOT IMPLEMENTED** (only envelope content identity exists).
* **Approval repository:** **NOT IMPLEMENTED**. The pattern-mining repository stores
  mining reports, not envelopes or approval decisions.
* **Approval owner:** external governance/human review is required by the declared
  boundary; a concrete named owner/authority contract is **NOT SPECIFIED**.

## External boundary

The following must exist outside `learning_data` before the learning chain can begin:

* real, completed historical or live outcome facts sufficient to populate every
  required PR173 row field;
* the authoritative knowledge UUID/version to which all outcomes are attributed;
* the authoritative per-row replay digest and its externally governed derivation;
* one consistent outcome metric/unit and the actual finite outcomes;
* timezone-aware observation timestamps and any real feature, indicator, risk, and
  context facts used for attribution;
* for PR175, unique sample identities and real feature, market, entry, exit, risk,
  outcome, and timestamp facts;
* an external review/approval decision authorizing exactly those samples; and
* an evidence handoff capable of producing the exact lineage-bound PR175 envelope.

Nothing in that list may be inferred from empty directories, generated from test
fixtures, recovered by choosing a latest file, or synthesized by bootstrap. In
particular, outcomes, sample UUIDs, knowledge identity, replay digests, timestamps,
contexts, approval, and approver authority must never be fabricated.

The operator must always select and supply the real governed source evidence and its
authoritative identities. At PR175 the operator/external governance boundary must
also supply the separately approved exact sample set. The repository does not define
a safe file argument or manual JSON/CSV procedure for doing so today.

## Lifecycle diagram

```text
external completed-outcome owner
  -> real immutable outcome facts + knowledge/replay provenance
  -> [governed PR173 acquisition/import composition: NOT IMPLEMENTED]
  -> KnowledgeOutcomeAttributionEngine.analyze(rows)
  -> KnowledgeOutcomeAttributionReport
  -> KnowledgeOutcomeAttributionRepository
  -> GovernedLearningPolicyEngine.evaluate(report)
  -> GovernedLearningPolicyReport (normally >= 30 samples to be eligible)

external governance/human review
  -> exact approved sample set + approval authority
  -> [approval workflow/repository and PR175 envelope acquisition: NOT IMPLEMENTED]
  -> ApprovedPatternMiningEvidenceEnvelope
  + exact eligible GovernedLearningPolicyReport
  -> PatternMiningEngine.mine(policy, envelope)
  -> PatternMiningReport
  -> PatternMiningRepository
  -> PR176 and later governed learning stages
```

## Example evidence schema (non-instance)

No fake CSV, JSON, evidence instance, or UUID is provided. The only repository-backed
schema that can be shown without fabrication is this abstract row shape:

```text
PR173Row := mapping {
  knowledge_uuid: UUID,
  knowledge_version: non-empty string,
  timestamp: timezone-aware ISO-8601 value,
  replay_digest: 64-character hexadecimal string,
  outcome: finite number (not boolean),
  outcome_metric: non-empty value [PR173 does not type-check it],
  outcome_unit: non-empty value [PR173 does not type-check it],
  features?: string-keyed canonical-value mapping,
  indicators?: string-keyed canonical-value mapping,
  risk_factors?: string-keyed canonical-value mapping,
  context?: string-keyed canonical-value mapping,
  ...extra source-bound keys permitted
}
PR173Evidence := non-empty list-or-tuple<PR173Row>
```

This is an API contract description only. It is not a sanctioned serialization or
operator import format.

## Operator workflow: current and required

### Current truthful workflow

1. Run bootstrap inspection; an empty clone reports the external approved
   PR173/PR175 evidence boundary.
2. Stop. There is no canonical tracked command that accepts operator evidence and
   produces PR173 plus PR175 input.
3. Do not place hand-written reports in `learning_data`, use test constructors, or
   treat direct repository JSON writing as acquisition.

### Exact missing next PR

The next PR required is a **governed PR173/PR175 external evidence acquisition and
approval-boundary implementation**. At minimum it must define the currently absent
source artifact/schema and owner, preserve immutable raw evidence and authoritative
knowledge/replay/source identity, perform fail-closed mapping into PR173 rows through
the existing `analyze()` owner, persist only through its repository, and define the
separate human/external approval artifact/repository that produces the exact PR175
envelope. Its detailed file format, CLI name, arguments, identity derivation, and
owner cannot be stated from current repository evidence and must be architecture-
approved rather than inferred by this discovery.

## Failure matrix

| Condition | Existing result / truthful status | Operator action |
|---|---|---|
| Empty PR173 evidence | `MISSING_EVIDENCE` | acquire real governed evidence externally |
| No PR173 input file/CLI | **NOT IMPLEMENTED** | do not invent/manual-write; implement the next governed acquisition PR |
| Invalid row/type/nested value | `INVALID_EVIDENCE` or `INVALID_EVIDENCE_VALUE` | correct at authoritative source |
| Invalid knowledge UUID | `INVALID_KNOWLEDGE_IDENTITY` | supply authoritative identity |
| Mixed knowledge UUID/version | `MIXED_KNOWLEDGE_IDENTITIES` | create a single-identity evidence set |
| Invalid timestamp/no timezone | `INVALID_TIMESTAMP` | supply authoritative timezone-aware timestamp |
| Invalid supplied replay digest | `REPLAY_MISMATCH` | correct external replay provenance; never synthesize it |
| Mixed outcome metric/unit | `MIXED_OUTCOME_UNITS` | supply one consistent outcome contract |
| Fewer than PR174 configured minimum (default 30) | `REQUIRES_MORE_DATA` / `MINIMUM_SAMPLE_THRESHOLD_NOT_MET` | acquire more real outcomes |
| PR173 report UUID collision with different bytes | `APPEND_ONLY_REPORT_COLLISION` | audit corruption; never overwrite |
| Missing PR175 envelope | `MISSING_APPROVED_PATTERN_EVIDENCE` | complete external approval/acquisition boundary |
| PR175 approval act/owner record needed | **NOT IMPLEMENTED** | next governed PR must define it |
| Envelope/policy/source/replay/knowledge mismatch | fail-closed specific `MIXED_*` error | use one exact reviewed lineage |
| Envelope sample count differs from PR174 | `INVALID_STATISTICS` | provide exact matching approved samples |
| Duplicate sample identity | `DUPLICATE_EVIDENCE_IDENTITY` or `DUPLICATE_CONFLICTING_IDENTITY` | repair source evidence; do not renumber synthetically |
| Envelope digest/UUID tampering | digest/UUID mismatch error | reacquire the exact governed artifact |

## Final required answers

1. **Does a PR173 importer already exist?** No.
2. **If yes, where?** Not applicable; **NOT IMPLEMENTED**.
3. **If no, what exact component is missing?** A governed external-outcome
   acquisition/import composition (including raw source contract, ownership,
   identity/replay provenance, validation/mapping, and owner-engine invocation), plus
   the separate PR175 approval artifact/repository workflow.
4. **Can a real operator currently feed PR173?** Not through any tracked canonical
   CLI/workflow. Only an ungoverned low-level Python call can supply in-memory rows.
5. **What exact artifact is required?** For PR173, a non-empty, single-knowledge-
   identity collection of real immutable rows matching the structural contract
   above with authoritative replay provenance. For PR175, the exact matching
   content-addressed `ApprovedPatternMiningEvidenceEnvelope`; the repository does
   not yet implement the approval record/process that truthfully authorizes it.
6. **What exact next PR is required?** A governed PR173 outcome-evidence acquisition
   and PR175 approval-boundary PR, without changes to Runtime, Strategy, Executor,
   Risk, Writer, or Broker. Exact CLI/file design is not recoverable from existing
   evidence and must be explicitly approved in that PR rather than fabricated here.
