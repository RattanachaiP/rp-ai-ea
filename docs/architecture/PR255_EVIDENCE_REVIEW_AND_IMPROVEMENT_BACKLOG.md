# PR255 — Evidence Review and Improvement Backlog

PR255 is an offline, advisory-only conversion of explicitly selected authoritative
production evidence into `production_improvement_backlog.json`. Run it with one
`--evidence` argument per selected artifact:

```bash
python -m analysis.production_improvement_backlog \
  --evidence /review/production_trading_report.json \
  --evidence /review/pipeline_validation_report.json \
  --output-directory /review/output
```

The tool accepts only the authoritative basenames declared by PR255. Selected
snapshots are ordered by `(basename, SHA-256)` so source references (`S000001`,
`S000002`, ...) and output are independent of CLI argument order. Each source
record contains its reference, basename, digest, and `ANALYZED`,
`NO_ADVERSE_OBSERVATION`, or `PROVENANCE_ONLY` processing status. Re-selecting the
same path or an identical `(basename, SHA-256)` snapshot fails explicitly.

PR255 uses **snapshot-scoped item identity**: the complete selected-snapshot
SHA-256 is part of every item ID. Therefore reports with the same authoritative
basename and metric cannot collide. Item evidence uses `source_ref`, never a
basename as identity.

A backlog item exists only where a schema-specific rule can cite a measured
adverse value. Raw logs and exports are provenanced but are not interpreted
heuristically; their governed PR253/PR254 reports provide measurable inputs.
Unknown governed observations are retained in `unsupported_observations`; zero or
favorable observations create no item. Nothing is silently converted into a
speculative improvement.

Each item records its evidence pointer, occurrence frequency, measured business
impact, reproducibility classification, severity, deterministic priority,
recommended owning component, and `PENDING_HUMAN_REVIEW` status. Priority is
derived from severity alone (`CRITICAL=P0`, `HIGH=P1`, `MEDIUM=P2`, `LOW=P3`);
occurrence count never escalates it. Aggregate net profit has frequency marked
not applicable. Pipeline missing-stage frequency is explicitly event density
(`missing_stage_events_per_lifecycle`), which can exceed one and is not a failure
rate. Missing stages preserve unknown attribution and target human investigation.
Priority is triage ordering only. It is not approval, an implementation
instruction, a tuning decision, or authority to modify production.

The module does not import or invoke AI, Strategy, Runtime, Writer, Executor,
Broker, position management, learning, or promotion code. It cannot activate,
apply, optimize, tune, or remediate anything. Human review and separate approval
remain mandatory for every future change, and the cited evidence must remain the
change's traceable justification.
