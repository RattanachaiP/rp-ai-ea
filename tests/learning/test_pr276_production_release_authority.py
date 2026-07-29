"""PR276 authoritative evidence-chain, lifecycle, and adversarial tests."""
from dataclasses import replace
import hashlib
import pytest
from learning.deployment import DeploymentGovernanceAuthority,DeploymentRegistry,HumanApprovalRegistry
from learning.release import (ActivationRevocation,EmergencyRollbackAuthorization,
 FinalGovernanceApprovalRecord,FinalGovernanceRegistry,ProductionReleaseAuthority,
 ProductionReleaseGovernanceBundle,RegistryMembershipEvidence,ReleaseCertificateRevocation,
 ReleasePolicy,ReleaseRegistry,RollbackArtifact,RollbackManifest,RuntimeActivationRegistry,
 TargetRuntimeInstance)
from tests.learning.test_pr275_deployment_governance import components as deployment_components
from tests.learning.test_pr275_deployment_governance import promoted as promoted_fixture

@pytest.fixture(scope="module")
def context(promoted_fixture):
    source=deployment_components(promoted_fixture)
    deployment_bundle=__import__('learning.deployment',fromlist=['DeploymentGovernanceBundle']).DeploymentGovernanceBundle(**source)
    result=DeploymentGovernanceAuthority().assess(deployment_bundle)
    deployment_registry=DeploymentRegistry().append(result); entry=deployment_registry.entries[0]
    report=result.report; artifact=source['deployment_artifact']; approval=source['human_approval_record']
    policy=ReleasePolicy('release-v2',result.release_request.release_authority_identity,
      (report.deployment_policy_identity,),(report.runtime_contract_identity,),
      'LIVE_PRODUCTION',approval.required_reviewer_role,'legacy-plan',hashlib.sha256(b'legacy').hexdigest(),'final-authority')
    runtime=TargetRuntimeInstance('v27-primary',report.target_environment_identity,report.runtime_contract_identity,'V27_PRODUCTION_EXECUTOR','27.1',7)
    rollback=RollbackArtifact('rollback-276',hashlib.sha256(b'rollback').hexdigest(),artifact.artifact_identity,
      runtime.runtime_contract_identity,runtime.executor_identity,runtime.executor_version)
    compatibility={'rollback_artifact_identity':rollback.artifact_identity,'target_artifact_identity':artifact.artifact_identity,
      'runtime_contract_identity':runtime.runtime_contract_identity,'executor_identity':runtime.executor_identity}
    rollback_manifest=RollbackManifest(rollback.artifact_identity,artifact.artifact_identity,runtime.target_environment_identity,
      runtime.runtime_contract_identity,runtime.executor_identity,compatibility)
    artifact_evidence=RegistryMembershipEvidence('artifact-registry','artifact-entry',artifact.artifact_identity,artifact.content_hash,'DEPLOYMENT_ARTIFACT')
    rollback_evidence=RegistryMembershipEvidence('rollback-registry','rollback-entry',rollback.artifact_identity,rollback.content_hash,'ROLLBACK_ARTIFACT')
    final=FinalGovernanceApprovalRecord(result.result_identity,result.release_request.request_identity,artifact.artifact_identity,
      policy.policy_identity,'final-authority','governor-1','APPROVED','2026-07-29T09:20:00Z','2026-07-29T10:00:00Z')
    values=dict(deployment_result=result,deployment_registry_entry=entry,deployment_registry=deployment_registry,
      human_approval_record=approval,human_approval_registry=source['human_approval_registry'],deployment_artifact=artifact,
      artifact_registry_evidence=artifact_evidence,rollback_artifact=rollback,rollback_manifest=rollback_manifest,
      rollback_registry_evidence=rollback_evidence,release_policy=policy,final_governance_record=final,
      final_governance_registry=FinalGovernanceRegistry().append(final),target_runtime_instance=runtime,
      assessed_at='2026-07-29T09:30:00Z')
    values['_deployment_source']=source
    return values

def bundle(context,**changes):
    values={k:v for k,v in context.items() if not k.startswith('_')}; values.update(changes)
    return ProductionReleaseGovernanceBundle(**values)

def test_authoritative_chain_emits_only_bound_activation(context):
    value=bundle(context); decision=ProductionReleaseAuthority().assess(value)
    assert decision.decision=='PRODUCTION_RELEASE_AUTHORIZED'
    assert all(g.passed for g in decision.evidence.gates)
    c,a=decision.certificate,decision.runtime_activation_authorization
    assert a.runtime_activation_authorized and not a.broker_access_authorized and not a.trade_execution_authorized
    assert (a.executor_identity,a.executor_version,a.runtime_instance_identity,a.activation_generation)==(
      c.executor_identity,c.executor_version,c.runtime_instance_identity,c.activation_generation)

def test_missing_or_superseded_deployment_registry_membership_fails(context):
    rejected=ProductionReleaseAuthority().assess(bundle(context,deployment_registry=DeploymentRegistry()))
    assert rejected.decision=='PRODUCTION_RELEASE_REJECTED'
    source=context['_deployment_source']|{'assessed_at':'2026-07-29T09:31:00Z'}
    upstream=__import__('learning.deployment',fromlist=['DeploymentGovernanceBundle']).DeploymentGovernanceBundle(**source)
    result2=DeploymentGovernanceAuthority().assess(upstream)
    registry=context['deployment_registry'].append(result2,context['deployment_registry_entry'].entry_identity)
    rejected=ProductionReleaseAuthority().assess(bundle(context,deployment_registry=registry))
    assert rejected.decision=='PRODUCTION_RELEASE_REJECTED'

def test_revoked_human_and_final_approval_reuse_fail(context):
    approval=context['human_approval_record']
    revoked=replace(approval,decision='REVOKED',issued_at='2026-07-29T09:25:00Z',expires_at='2026-07-29T10:00:00Z',supersedes_record_identity=approval.record_identity,record_identity='')
    approvals=context['human_approval_registry'].append(revoked)
    assert ProductionReleaseAuthority().assess(bundle(context,human_approval_registry=approvals)).decision=='PRODUCTION_RELEASE_REJECTED'
    final=context['final_governance_record']
    revoked_final=replace(final,decision='REVOKED',issued_at='2026-07-29T09:25:00Z',supersedes_record_identity=final.record_identity,record_identity='')
    finals=context['final_governance_registry'].append(revoked_final)
    assert ProductionReleaseAuthority().assess(bundle(context,final_governance_registry=finals)).decision=='PRODUCTION_RELEASE_REJECTED'

def test_forged_final_record_and_rollback_incompatibility_fail(context):
    final=replace(context['final_governance_record'],authority_identity='attacker',record_identity='')
    rejected=ProductionReleaseAuthority().assess(bundle(context,final_governance_record=final,final_governance_registry=FinalGovernanceRegistry().append(final)))
    assert rejected.decision=='PRODUCTION_RELEASE_REJECTED'
    with pytest.raises(ValueError,match='ROLLBACK_COMPATIBILITY'):
      replace(context['rollback_manifest'],compatibility_evidence={'executor_identity':'wrong'},manifest_identity='')

def test_activation_is_single_use_time_bound_and_target_bound(context):
    activation=ProductionReleaseAuthority().assess(bundle(context)).runtime_activation_authorization
    registry=RuntimeActivationRegistry().register(activation)
    with pytest.raises(ValueError,match='ACTIVATION_REPLAY'): registry.register(activation)
    with pytest.raises(ValueError,match='ACTIVATION_EXPIRED'): registry.consume(activation,activation.executor_identity,activation.executor_version,activation.runtime_instance_identity,'2026-07-29T10:00:00Z')
    with pytest.raises(ValueError,match='TARGET_MISMATCH'): registry.consume(activation,'wrong',activation.executor_version,activation.runtime_instance_identity,'2026-07-29T09:31:00Z')
    consumed=registry.consume(activation,activation.executor_identity,activation.executor_version,activation.runtime_instance_identity,'2026-07-29T09:31:00Z')
    with pytest.raises(ValueError,match='ACTIVATION_REPLAY'): consumed.consume(activation,activation.executor_identity,activation.executor_version,activation.runtime_instance_identity,'2026-07-29T09:32:00Z')
    assert consumed.transition(activation,'ACTIVE','2026-07-29T09:32:00Z').entries[-1].state=='ACTIVE'

def test_certificate_cross_binding_registry_scope_and_revocation(context):
    decision=ProductionReleaseAuthority().assess(bundle(context)); manifest=decision.release_manifest
    with pytest.raises(ValueError,match='DECISION_BINDING'):
      replace(decision,release_manifest=replace(manifest,executor_identity='wrong',manifest_identity=''),decision_identity='')
    registry=ReleaseRegistry().append(decision)
    revoked=ReleaseCertificateRevocation(decision.certificate.certificate_identity,'release-authority','incident','2026-07-29T09:32:00Z')
    registry=registry.revoke_certificate(revoked)
    assert registry.certificate_revocations[-1]==revoked
    activation_revocation=ActivationRevocation(decision.runtime_activation_authorization.authorization_identity,'release-authority','incident','2026-07-29T09:32:00Z')
    registry=registry.revoke_activation(activation_revocation)
    rollback=EmergencyRollbackAuthorization(decision.certificate.certificate_identity,decision.certificate.rollback_manifest_identity,
      decision.certificate.runtime_instance_identity,'emergency-authority','incident','2026-07-29T09:33:00Z')
    assert registry.authorize_rollback(rollback).rollback_authorizations[-1]==rollback
