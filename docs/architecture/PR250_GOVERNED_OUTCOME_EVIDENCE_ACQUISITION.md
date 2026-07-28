# PR250 Governed Outcome Evidence Acquisition

## Authority and schema

`learning.outcome_evidence` is the external-genesis acquisition owner. It owns the immutable input contract, validation, canonical raw admission, source manifest, replay provenance, and explicit operator composition into PR173. `KnowledgeOutcomeAttributionEngine.analyze()` remains the attribution owner and `KnowledgeOutcomeAttributionRepository` remains the PR173 report owner. Acquisition performs no learning policy, mining, PR175 approval, Runtime, Strategy, Risk, Writer, Executor, broker, `OrderSend`, position, or exit action.

The sole production format is UTF-8 JSON schema `PR250.OUTCOME_EVIDENCE.1.0` with exact fields `schema_version`, `source_system_identity`, `acquisition_timestamp`, `operator_metadata`, `declared_knowledge_identity`, `declared_outcome_contract`, `evidence_rows`, `manifest_digest`, and optional non-secret `external_source_reference`. This is a schema description, not evidence; the repository supplies no production-looking UUID.

Each immutable `OutcomeEvidenceRow` requires `knowledge_uuid`, `knowledge_version`, `timestamp`, `replay_digest`, `outcome`, `outcome_metric`, and `outcome_unit`. Optional fields are `features`, `indicators`, `risk_factors`, `context`, and explicitly governed `metadata`. Unknown fields are rejected. Timestamps are timezone-aware, outcomes finite, nested values canonical JSON with non-empty string keys, and all rows match the declared knowledge/outcome identities.

## Digest and identity model

PR250 chooses replay model **B**. The acquisition owner computes SHA-256 over the exact domain bytes `RP-AI-EA/PR250/ROW-REPLAY/V1` plus NUL and compact UTF-8 key-sorted finite canonical JSON of the complete normalized immutable row excluding only its carried `replay_digest`. External event/deal identity belongs in governed row metadata and is then cryptographically bound. A mismatch is `REPLAY_PROVENANCE_INVALID`; no arbitrary digest is accepted.

`manifest_digest` is SHA-256 over domain `RP-AI-EA/PR250/MANIFEST/V1\0` and the complete canonical manifest without its digest, with evidence order normalized. It binds source system, acquisition time, operator metadata, declarations, external reference, and rows. It differs from PR173 `source_digest`, which hashes only PR173's sorted full normalized rows. The evidence UUID is UUIDv5 in PR250's fixed namespace named by `manifest_digest`. PR173 retains ownership of attribution UUID and report replay digest. Same UUID/different bytes is a collision and is never overwritten.

## Repository

Raw records live at `learning_data/outcome_evidence/evidence_<evidence_uuid>.json`. They preserve the complete normalized manifest/rows, source manifest and digest, source digest, record UUID, replay binding, acquisition/source/schema/import provenance, and record integrity digest. Compact canonical JSON is atomically linked from an fsynced temporary file. Same bytes replay idempotently; different bytes fail. Loads verify canonical bytes, manifest/replay identity, record digest, UUID, and filename. There is no overwrite, delete, or latest selection; lookup is exact UUID only. A pre-link interruption leaves no canonical record and is retry-safe.

## Operator workflow

Read-only PowerShell commands:

```powershell
$EvidenceFile = ".\real-governed-outcome-evidence.json"
python -m learning.outcome_evidence.operator_acquisition validate --input $EvidenceFile
python -m learning.outcome_evidence.operator_acquisition inspect
```

Mutating commands, each requiring an exact path or identity:

```powershell
python -m learning.outcome_evidence.operator_acquisition import --input $EvidenceFile
$EvidenceUuid = "real-uuid-returned-by-import"
python -m learning.outcome_evidence.operator_acquisition inspect --evidence-uuid $EvidenceUuid
python -m learning.outcome_evidence.operator_acquisition construct-pr173 --evidence-uuid $EvidenceUuid
```

`validate` computes prospective identities without creating `learning_data`. `inspect` verifies all records or one exact record without writes. `import` writes only raw evidence. `construct-pr173` verifies exactly one record, reconstructs exact rows, invokes the existing PR173 engine, persists through its repository, verifies source/replay digests, and returns the deterministic attribution UUID. Both mutations are idempotent. Put `--base <exact-learning-data-root>` before the subcommand for a non-default root.

## Failure and recovery

Every diagnostic reports `mutation_occurred`, `rerun_safe`, and exact `next_action`.

| Diagnostic | Recovery |
|---|---|
| `OUTCOME_EVIDENCE_FILE_MISSING` | supply the exact real path, or import the selected record first |
| `OUTCOME_EVIDENCE_SCHEMA_INVALID` | correct and re-export at the authoritative source |
| `OUTCOME_EVIDENCE_EMPTY` | acquire at least one real completed outcome |
| `OUTCOME_EVIDENCE_IDENTITY_MISMATCH` | split/select one exact knowledge/evidence identity |
| `OUTCOME_CONTRACT_MISMATCH` | split evidence by exact metric/unit |
| `TIMESTAMP_INVALID` | supply authoritative timezone-aware ISO-8601 time |
| `REPLAY_PROVENANCE_INVALID` | re-export complete immutable event and PR250 replay digest |
| `SOURCE_DIGEST_MISMATCH` | re-export canonical manifest; do not hand-edit |
| `EVIDENCE_REPOSITORY_CORRUPT` | restore from governed source and audit repository |
| `AMBIGUOUS_EVIDENCE_IDENTITY` | quarantine/audit; never overwrite or choose one |
| `PR173_RESULT_PROVENANCE_MISMATCH` | quarantine result and audit canonicalization |
| `PR173_CONSTRUCTION_FAILED` | audit record and retry the exact evidence UUID |

## PR175 handoff and fresh-clone limitation

PR250 does not approve evidence or construct `ApprovedPatternMiningEvidenceEnvelope`. It retains exact rows, contexts, metadata, timestamps, outcomes, knowledge/outcome identities, replay/source/manifest digests, and source evidence UUID. PR251 must define a human approval owner and append-only approval record that maps exact rows into PR175 samples and binds approver, approval timestamp, decision, envelope UUID, and PR250 evidence UUID before deterministic envelope construction. No PR250 state means approval.

On a clone without `learning_data`, inspect reports zero and validate does not mutate. Given a **real** conforming operator file, import creates one raw record, replay is idempotent, explicit construction persists exact PR173, and inspect exposes exact identities. The repository cannot generate source data, knowledge UUID, timestamps, outcomes, external identity, or operator authority. PR174–PR179 and pending PR175 approval must still complete before PR248 crosses genesis; PR250 alone is not production readiness and changes no trading authority.
