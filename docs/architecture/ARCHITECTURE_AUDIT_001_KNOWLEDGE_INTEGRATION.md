# Architecture Audit-001 — Knowledge Integration

**Audit date:** 2026-07-23  
**Baseline audited:** `7cee754` (`Learning-005: Add statistical validation engine`)  
**Scope:** production Python under `brain/`, `learning/`, and `runtime/`, plus the
Decision Publisher boundary. Tests and legacy bridge learning-state files are not
treated as integration consumers because they are outside the current Brain →
Runtime pipeline.

## Result

**FAIL — four architecture violations.** The required zero-violation acceptance
criterion is not met at the audited baseline. This is an audit-only change: no
production behavior has been changed and the violations are documented rather
than refactored.

## Method

The audit used source inspection and static import inspection. The import check
parses each production Python module with `ast` and lists imports rooted at
`brain`, `learning`, `runtime`, or `bridge`. The storage check searches the
Learning package for `Path`, file-open/read, directory, glob, and atomic-write
operations. The promotion and immutability checks inspect all references to
`promote`, `save_knowledge`, and `VerifiedKnowledge`.

Commands used:

```bash
python -m pytest tests/learning tests/test_decision_pipeline.py \
  tests/test_writer_adapter.py tests/test_decision_publication.py \
  tests/test_executor_integration.py
python -m pytest
python - <<'PY'
import ast
from pathlib import Path
for root in ("brain", "runtime", "learning", "bridge"):
    for path in sorted(Path(root).rglob("*.py")):
        tree = ast.parse(path.read_text())
        # Inspect Import and ImportFrom nodes rooted at the audited packages.
PY
rg -n --glob '*.py' '(Path\\(|\\.open\\(|\\.read_text\\(|\\.write_text\\(|\\.glob\\(|\\.mkdir\\(|os\\.(link|replace|fsync))' learning
rg -n --glob '*.py' 'promote\\(|save_knowledge|VerifiedKnowledge|KnowledgeReader' brain learning runtime
```

## Dependency Graph

```text
CandidatePattern
    │
    ├── PatternRepository ──> PatternStorage ──> learning_data/patterns/*.json
    │
    └── StatisticalValidator ──> ValidationRepository
                                      ├── validation_results/*.json
                                      └── verified_patterns/*.json (VerifiedKnowledge)

Brain DecisionPipeline ──> WriterAdapter ──> DecisionPublisher ──> decision.json
                                              │
Executor <── bridge.decision_writer <─────────┘

Required but absent: Decision Engine ──> KnowledgeReader ──> Knowledge Repository
```

There is no production import edge from `brain` or `runtime` to `learning`.
There is also no `KnowledgeReader` symbol anywhere in the audited production
packages. Consequently, the current Decision Engine does not access knowledge
storage directly, but it also has no approved reader-mediated knowledge
consumption path.

## Audit Matrix

| # | Control | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Decision Engine consumes KnowledgeReader only; no direct storage access | **FAIL** | `KnowledgeReader` is absent, and `brain/decision_pipeline.py` imports only Brain modules. No direct storage access was found, but required knowledge consumption cannot be verified. |
| 2 | Repository is the only storage abstraction; no file access outside repository | **FAIL** | `learning/pattern/storage.py` owns filesystem persistence directly as `PatternStorage`, rather than a repository. |
| 3 | Validation Engine is the only promotion authority | **FAIL** | The standalone, publicly exported `promote()` function can construct `VerifiedKnowledge` from any caller-supplied `VERIFIED` result without invoking `StatisticalValidator`. |
| 4 | Knowledge Repository is append-only | **PASS** | `ValidationRepository._append()` returns byte-identical existing records and rejects differing existing content; it creates new files with exclusive creation/linking. |
| 5 | Knowledge is immutable | **FAIL** | `VerifiedKnowledge` is a frozen dataclass but stores mutable `dict` fields without defensive conversion to immutable mappings. |
| 6 | Runtime cannot modify Knowledge | **PASS** | Static imports show no `runtime` → `learning` edge; runtime code has no Knowledge repository dependency. |
| 7 | Executor has zero dependency on Learning | **PASS** | `runtime/executor.py` imports only `bridge.decision_writer` and runtime broker-safety contracts. |
| 8 | Writer has zero dependency on Learning | **PASS** | `runtime/writer_adapter.py` imports only `brain.decision_pipeline`; `bridge/decision_writer.py` has no Learning import. |
| 9 | Decision Publisher remains isolated | **PASS** | `runtime/decision_publication.py` imports only runtime Writer Adapter contract types and owns only `decision.json` publication. |
| 10 | Imports follow Knowledge-integration dependency rules | **PASS, with item 1 limitation** | No prohibited `brain`/`runtime` → `learning` imports exist. The missing required `brain` → `KnowledgeReader` edge is recorded as item 1 rather than counted twice. |

## Violation Report

### A001-01 — Missing KnowledgeReader integration (P0)

**Rule affected:** Decision Engine must consume Knowledge through `KnowledgeReader`
only.  
**Evidence:** no `KnowledgeReader` implementation or import exists. The Decision
Pipeline composes only Brain-domain engines.  
**Impact:** knowledge consumption and its repository boundary are unprovable; the
required integration contract has not been implemented.

### A001-02 — PatternStorage is a parallel storage abstraction (P0)

**Rule affected:** Repository is the only storage abstraction and filesystem
access must not occur outside it.  
**Evidence:** `PatternStorage` creates directories, opens files, reads JSON, globs
files, and performs atomic links. `PatternRepository` delegates persistence to
this separately named abstraction.  
**Impact:** the repository-only storage boundary is split and cannot be enforced
at one type/API boundary.

### A001-03 — Promotion is publicly callable outside StatisticalValidator (P0)

**Rule affected:** Validation Engine is the sole promotion authority.  
**Evidence:** `learning.validation.verifier.promote()` is a module-level function
and is re-exported by `learning.validation`. It only checks a caller-provided
result status before returning `VerifiedKnowledge`.  
**Impact:** a caller can construct a `ValidationResult(..., "VERIFIED", ...)` and
call `promote()` without executing the validation engine's checks.

### A001-04 — VerifiedKnowledge is shallowly mutable (P0)

**Rule affected:** Knowledge must remain immutable.  
**Evidence:** its frozen dataclass fields `conditions` and `statistics` are plain
`dict` objects; freezing the dataclass prohibits rebinding but not mutation such
as `knowledge.conditions["key"] = value`.  
**Impact:** the in-memory object can diverge from the append-only persisted
record after promotion.

## Recommended Fixes (Not Implemented)

1. Define a read-only `KnowledgeReader` interface owned by the knowledge
   repository boundary, then make the Decision Engine depend on that interface
   only—never on paths, JSON, or repository implementation types.
2. Fold `PatternStorage`'s filesystem operations into `PatternRepository` (or
   rename and formalize it as the sole repository) so all Learning persistence
   is exposed through one repository abstraction per store.
3. Make promotion an internal `StatisticalValidator` operation and remove the
   public `promote` export. Construct verified knowledge only after the
   validator has produced its own verified result.
4. Convert `VerifiedKnowledge.conditions` and `.statistics` to defensive,
   read-only mappings (and recursively freeze nested values if those are
   allowed) before persistence and reader exposure.
5. Add static architecture tests that fail on (a) missing Decision Engine →
   `KnowledgeReader`, (b) direct Learning filesystem access outside repository
   modules, (c) public promotion entry points, (d) mutable knowledge fields,
   and (e) `runtime`/Writer/Executor imports of Learning.

## Positive Isolation Findings

Runtime isolation remains intact at the baseline: the Writer Adapter translates
Brain `DecisionPackage` values, the Publisher serializes only the adapter
payload, and the Executor accepts a Writer read snapshot. None imports or
modifies the Learning package. The Knowledge Repository's persisted records are
also append-only; the audit failures concern the missing reader integration,
parallel storage boundary, public promotion function, and in-memory knowledge
mutability.
