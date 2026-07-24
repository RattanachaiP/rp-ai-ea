# PR152 Knowledge Policy Engine

`learning.policy` is an offline, deterministic, read-only eligibility evaluator. It consumes caller-supplied immutable knowledge, governance, lifecycle, and analytics snapshots and produces an append-only policy report. It does not import Decision Engine, runtime, executor, or broker modules; it has no promotion, retirement, lifecycle, governance, analytics, or runtime mutation API.

Policy configuration is represented by `PolicyConfig`; every threshold and its version are explicit inputs. The seven independently callable rule categories are `SamplePolicy`, `PerformancePolicy`, `StabilityPolicy`, `ConflictPolicy`, `LifecyclePolicy`, `GovernancePolicy`, and `SchemaPolicy`. `SchemaPolicy` additionally emits an analytics freshness warning. Reports are persisted atomically under `learning_data/policy/evaluation_<evaluation_uuid>.json` and cannot be overwritten with different content.

Use the offline command with `python -m learning.policy.run KNOWLEDGE.json --source-baseline COMMIT`; add `--governance`, `--analytics`, `--config`, `--lifecycle-state`, `--timestamp`, and `--persist` as required. The command evaluates supplied files only and does not access runtime state.
