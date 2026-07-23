# RAIP Schema Registry

All cross-domain JSON documents are versioned contracts. Every producer MUST emit
`schema_version` and `producer`; every consumer MUST verify that its supported version is
compatible before reading any semantic field. Unknown major versions are rejected safely.

| Contract | Current version | Producer | Consumer |
| --- | --- | --- | --- |
| Evidence | 2.0.0 | Evidence Domain | Knowledge and later passive domains |
| Recommendation | 5.0.0 | Recommendation Domain | Governance, Executive |
| Governance report | 6.0.0 | Governance Domain | Executive |
| Executive decision package | 7.0.0 | Executive Domain | Simulation & Validation |
| Historical replay / scenarios / validation | 9.0.0 | Simulation & Validation Domain | Validation repository / human review |
| Learning intake policy / report / lineage / registry / readiness | 10.0.0 | Learning Intake Domain | Future Learning Engine / human review |

The machine-readable V9 contract schemas are maintained in `review_engine/schemas/`.

V10 canonical naming is governed by `docs/architecture/RAIP_VERSION_REGISTRY.md`.
