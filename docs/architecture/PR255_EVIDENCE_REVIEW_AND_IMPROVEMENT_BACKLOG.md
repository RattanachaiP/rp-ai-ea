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

The tool accepts only the authoritative basenames declared by PR255 and records a
SHA-256 digest for every selected source. A backlog item exists only where a
schema-specific rule can cite a measured adverse value. Raw logs and exports are
provenanced but are not interpreted heuristically; their governed PR253/PR254
reports provide the measurable inputs. Zero, favorable, unknown, missing, or
unsupported observations never become speculative improvements.

Each item records its evidence pointer, occurrence frequency, measured business
impact, reproducibility classification, severity, deterministic priority,
recommended owning component, and `PENDING_HUMAN_REVIEW` status. Priority is
triage ordering only. It is not approval, an implementation instruction, a tuning
decision, or authority to modify production.

The module does not import or invoke AI, Strategy, Runtime, Writer, Executor,
Broker, position management, learning, or promotion code. It cannot activate,
apply, optimize, tune, or remediate anything. Human review and separate approval
remain mandatory for every future change, and the cited evidence must remain the
change's traceable justification.
