# PR #139 — Repository Schema Report

## Result: PASS

Schema ownership and versions are aligned across the registry, domain implementation constants,
and V10 policy:

| Domain/document family | Canonical version | Verification |
| --- | --- | --- |
| Evidence | `2.0.0` | Registry-owned cross-domain contract. |
| Recommendation | `5.0.0` | Registry-owned cross-domain contract. |
| Governance report | `6.0.0` | Governance producer metadata. |
| Executive decision package | `7.0.0` | Executive producer and V9 input gate. |
| Simulation/validation | `9.0.0` | Simulation producer and V10 policy input. |
| Learning intake | `10.0.0` | Learning Intake producer and policy accepted output. |

V10 validates its policy's required fields and exact source schema versions before qualification.
V9 rejects an executive package outside major version 7 rather than applying fallback semantics.
The registry correctly records V8 as unassigned; no schema claims V8 authority.

No schema migration is required by PR #139.
