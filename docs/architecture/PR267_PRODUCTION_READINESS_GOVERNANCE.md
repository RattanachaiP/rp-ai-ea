# PR267 Production Readiness Governance

## Purpose

PR267 is a governed, read-only layer above PR266 Operational Qualification. It answers one
question: **is the accumulated, integrity-verified qualification evidence sufficient to be
submitted to a human production reviewer?** It does not answer whether deployment should
occur and cannot perform deployment.

## Contracts and flow

1. `ProductionReadinessPolicy` fixes campaign, stability, duration, failure, recovery,
   evidence-density, qualification-version, and architecture-version requirements under a
   deterministic identity.
2. `ProductionReadinessCandidate` directly embeds the authoritative `QualificationRegistry`,
   `QualificationReport`, `CampaignStatistics`, readiness policy, architecture version,
   repository commit, generation, and predecessor identity. Construction revalidates every
   embedded identity and cross-report binding.
3. `ProductionReadinessRegistry` returns a new immutable snapshot for each append. It rejects
   duplicate candidates, skipped generations, broken predecessors, and policy changes.
4. `ProductionReadinessReport` recomputes governed measurements from the bound evidence and
   fails closed to `NOT_READY`. Sufficient evidence produces only
   `READY_FOR_HUMAN_REVIEW`.
5. `ProductionReadinessLifecycle` records forward-only, identity-chained events from named
   human actors. Review may reach `APPROVED_FOR_DEPLOYMENT` or `REJECTED`; either terminal
   decision may later be `SUPERSEDED`.
6. `ProductionReadinessAuditor` checks qualification and campaign lineage, policy and
   architecture versions, repository commit, report integrity, and human approval history.

## Lifecycle

```text
NOT_READY
READY_FOR_HUMAN_REVIEW -> UNDER_HUMAN_REVIEW
UNDER_HUMAN_REVIEW -> APPROVED_FOR_DEPLOYMENT | REJECTED
APPROVED_FOR_DEPLOYMENT | REJECTED -> SUPERSEDED
```

`NOT_READY` has no transition. New evidence must produce a new candidate and report. Reverse
transitions are rejected. Every review transition requires an actor identity prefixed with
`HUMAN:` and becomes part of the immutable report identity.

## Authority boundary

The implementation imports no Runtime, Executor, strategy, broker, or OrderSend interface.
All contracts are frozen values and all registry operations create new snapshots. The layer
may observe, validate, aggregate, audit, record, and report only. The report fields
`production_authorized` and `deployment_performed` are invariantly false—even for
`APPROVED_FOR_DEPLOYMENT`. Human approval is evidence, not executable authority.

The layer does not modify qualification policy or history, execution plans, strategy
thresholds, offline learning, or deterministic replay inputs. V27 remains the existing
production execution authority.
