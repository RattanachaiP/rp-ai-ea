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
   governed `RepositoryEvidence`, generation, and predecessor identity. Repository evidence
   requires a full commit digest and an identity-bound governed observer attestation;
   construction revalidates every embedded identity and cross-report binding.
3. `ProductionReadinessRegistry` returns a new immutable snapshot for each append. It rejects
   duplicate candidates, skipped generations, broken predecessors, policy changes, and
   semantically duplicate submissions with no new qualification-registry generation.
4. `ProductionReadinessReport` recomputes governed measurements from the bound evidence and
   fails closed to `NOT_READY`. Sufficient evidence produces only
   `READY_FOR_HUMAN_REVIEW`.
5. `ProductionReadinessLifecycle` records forward-only, identity-chained events from governed
   human identities. The identity authority grants explicit reviewer, approver, and governance
   owner roles. Event timestamps must increase strictly; reviewers cannot approve or reject
   their own review. Either terminal decision may later be `SUPERSEDED`.
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
transitions are rejected. Governed identity, acting role, timestamp, reason, predecessor, and
event identity become part of the immutable report identity.

## Authoritative evidence and metrics

PR267 does not recreate PR266 qualification rules. `QualificationReport.status`,
`operational_recommendation`, and `stable_campaign_count` are authoritative. The latter is
used for both the qualified-campaign and consecutive-stable-campaign readiness thresholds;
PR267 never infers qualification merely from nested certification PASS values.

Runtime coverage is the sum of each validated campaign's first-to-last qualification-run
interval. Time between campaigns is explicitly excluded. Evidence density is the total number
of authoritative run observations divided by those validated coverage hours; it is not an
inter-campaign wall-clock rate and does not count gaps as either runtime or denominator.

The report builder reconstructs candidate and registry contracts and raises immediately for
integrity, policy-binding, or current-candidate failures. Only valid but insufficient evidence
produces `NOT_READY`. The auditor independently recomputes coverage, rates, density, readiness
status, evidence bindings, approval chronology, roles, separation of reviewer and approver,
event lineage, and terminal status.

## Authority boundary

The implementation imports no Runtime, Executor, strategy, broker, or OrderSend interface.
All contracts are frozen values and all registry operations create new snapshots. The layer
may observe, validate, aggregate, audit, record, and report only. The report fields
`production_authorized` and `deployment_performed` are invariantly false—even for
`APPROVED_FOR_DEPLOYMENT`. Human approval is evidence, not executable authority.

The layer does not modify qualification policy or history, execution plans, strategy
thresholds, offline learning, or deterministic replay inputs. V27 remains the existing
production execution authority.
