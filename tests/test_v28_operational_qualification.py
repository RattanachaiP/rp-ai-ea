"""PR266 authoritative evidence, policy, continuity, lineage and fail-closed tests."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import pytest
from bridge.v28.campaign_statistics import aggregate_campaign_statistics
from bridge.v28.certification_report import build_certification_report
from bridge.v28.delivery_reliability_validator import validate_delivery_reliability
from bridge.v28.execution_bridge import DeliveryReceipt
from bridge.v28.execution_plan import identity
from bridge.v28.operational_readiness import assess_operational_readiness
from bridge.v28.pipeline_validator import certification_identity,create_campaign
from bridge.v28.publisher_contract import PublishedExecutionPlan,RuntimeHealthSnapshot
from bridge.v28.qualification_campaign import (canonical_utc,create_qualification_campaign,
 create_qualification_run,create_recovery_evidence,create_runtime_sample,create_scenario,
 normalized_projection_identity,semantic_output_identity)
from bridge.v28.qualification_policy import create_qualification_policy
from bridge.v28.qualification_registry import QualificationRegistry,create_registry
from bridge.v28.qualification_report import build_qualification_report
from bridge.v28.runtime_certifier import certify_runtime
from bridge.v28.runtime_stability_monitor import monitor_runtime_stability
from bridge.v28.shadow_campaign_runner import run_shadow_campaign
from tests.test_v28_end_to_end_validation import chain,receipt_for,reports

BASE=datetime(1970,1,1,0,1,40,tzinfo=timezone.utc)
def stamp(n,offset="Z"):
    value=BASE+timedelta(seconds=n)
    if offset=="Z":return value.isoformat().replace("+00:00","Z")
    return value.astimezone(timezone(timedelta(hours=1))).isoformat()
def rebound(obj,domain,**changes):
    values=obj.canonical_payload();values.update(changes)
    field="publication_replay_identity" if type(obj) is PublishedExecutionPlan else "replay_identity"
    digest=identity(domain,values) if domain.startswith("V28_EXECUTION_") or domain=="V28_DELIVERY_RECEIPT_REPLAY" else certification_identity(domain,values)
    return type(obj)(**values,**{field:digest})
def certification_variant(index,publication,sequence=None):
    p,replay,shadow,delivery,_,_=reports();old=p.campaign
    campaign=create_campaign(runtime_sequence_id=sequence if sequence is not None else 100+index,symbol=old.symbol,evaluation_time=stamp(index),decision_replay_identity=old.decision_replay_identity,plan_replay_identity=old.plan_replay_identity,publication_replay_identity=publication.publication_replay_identity,environment_identity=old.environment_identity)
    p=rebound(p,"V28_PIPELINE_VALIDATION",campaign=campaign);replay=rebound(replay,"V28_REPLAY_CONSISTENCY",campaign=campaign);shadow=rebound(shadow,"V28_SHADOW_VALIDATION",campaign=campaign);delivery=rebound(delivery,"V28_DELIVERY_VALIDATION",campaign=campaign)
    runtime=certify_runtime(p,delivery);ready=assess_operational_readiness(p,replay,shadow,delivery,runtime)
    return build_certification_report(p,replay,shadow,delivery,runtime,ready)
def policy(**changes):
    values=dict(minimum_campaign_duration_seconds=14,minimum_run_count=15,minimum_runs_per_action=5,maximum_heartbeat_gap_seconds=2,expiry_after_seconds=40);values.update(changes)
    return create_qualification_policy(**values)
def campaign_fixture(*,heartbeat_gap=False,sequence_gap=False,utc_offset=False,policy_value=None,lineage=None,start=0):
    pol=policy_value or policy();args,environment,_=chain();base_pub=args["publication"];base_health=args["health"];base_receipt=receipt_for(args,environment);runs=[];previous=None
    for i in range(15):
        seq=100+i+(1 if sequence_gap and i>=8 else 0);when=start+i;action=("BUY","SELL","HOLD")[i%3]
        pub=rebound(base_pub,"V28_EXECUTION_PUBLICATION_REPLAY",runtime_sequence_id=seq,publication_timestamp=stamp(when))
        cert=certification_variant(when,pub,seq);campaign=cert.campaign
        receipt_values=base_receipt.canonical_payload();receipt_values.update(publication_replay_identity=pub.publication_replay_identity,environment_identity=campaign.environment_identity,runtime_sequence_id=seq,delivered_at=stamp(when))
        receipt=DeliveryReceipt(**receipt_values,replay_identity=identity("V28_DELIVERY_RECEIPT_REPLAY",receipt_values))
        heartbeat=stamp(when-5 if heartbeat_gap and i==8 else when)
        health=rebound(base_health,"V28_RUNTIME_HEALTH_SNAPSHOT_REPLAY",runtime_sequence_id=seq,observed_at=heartbeat,evaluation_time=stamp(when),expires_at=stamp(when+5))
        sample=create_runtime_sample(health=health,runtime_sequence=seq,heartbeat_at=heartbeat,observed_at=heartbeat,health_status="HEALTHY",source_identity=health.source_authority,environment_identity=campaign.environment_identity,policy_reference=health.policy_reference)
        fixture=f"fixture-{action}";normalized=normalized_projection_identity(family_identity="family",fixture_identity=fixture,symbol=campaign.symbol,environment_identity=campaign.environment_identity,action=action)
        scenario=create_scenario(family_identity="family",action=action,fixture_identity=fixture,normalized_input_identity=normalized,expected_semantic_output_identity=semantic_output_identity(cert,action))
        recovery=create_recovery_evidence(status="NONE",source_identity="RECOVERY_AUDITOR",observed_at=stamp(when),campaign_identity=campaign.campaign_identity)
        run=create_qualification_run(ordinal=i+1,symbol=campaign.symbol,environment_identity=campaign.environment_identity,runtime_sequence=seq,evaluation_time=stamp(when,offset="+01:00" if utc_offset else "Z"),scenario=scenario,runtime_sample=sample,publication=pub,pipeline=cert.architecture,delivery=cert.delivery,receipt=receipt,certification=cert,recovery=recovery,previous_run_identity=previous,policy_identity=pol.policy_identity,pr265_campaign_identity=campaign.campaign_identity)
        runs.append(run);previous=run.run_identity
    return create_qualification_campaign(lineage_identity=lineage,started_at=stamp(start),symbol=runs[0].symbol,environment_identity=runs[0].environment_identity,scenario_family_identity="family",runs=runs,policy=pol)

def complete(c,at):
    registry=create_registry(c.policy).append(c,appended_at=at);stats=aggregate_campaign_statistics(registry);runtime=monitor_runtime_stability(c);shadow=run_shadow_campaign(c);delivery=validate_delivery_reliability(c)
    return build_qualification_report(c,registry,stats,runtime,shadow,delivery,assessed_at=at),registry,stats

def test_distinct_certifications_compare_semantics_and_qualify():
    c=campaign_fixture();assert len({x.certification.replay_identity for x in c.runs})==15
    report,_,stats=complete(c,stamp(20));assert report.status=="PASS" and report.operational_recommendation=="READY FOR HUMAN REVIEW" and not report.production_authorized
    assert stats.first_observed_at.endswith("Z") and stats.last_observed_at.endswith("Z")
def test_reused_certification_and_cross_run_boundaries_rejected():
    c=campaign_fixture()
    with pytest.raises(ValueError):replace(c.runs[1],certification=c.runs[0].certification,pr265_campaign_identity=c.runs[0].pr265_campaign_identity)
    bad=replace(c.runs[1]);object.__setattr__(bad,"certification",c.runs[0].certification);object.__setattr__(bad,"pipeline",c.runs[0].pipeline);object.__setattr__(bad,"delivery",c.runs[0].delivery);object.__setattr__(bad,"pr265_campaign_identity",c.runs[0].pr265_campaign_identity);object.__setattr__(bad,"run_identity",certification_identity("V28_QUALIFICATION_RUN",bad.canonical_payload()))
    with pytest.raises(ValueError):replace(c,runs=(c.runs[0],bad)+c.runs[2:],campaign_identity=c.campaign_identity)
    with pytest.raises(ValueError):replace(c,symbol="EURUSD")
    with pytest.raises(ValueError):replace(c,environment_identity="other")
    with pytest.raises(ValueError):replace(c.runs[0],pr265_campaign_identity="other")
def test_real_health_heartbeat_sequence_and_no_success_booleans():
    assert monitor_runtime_stability(campaign_fixture(heartbeat_gap=True)).status=="FAIL"
    with pytest.raises(ValueError,match="RUNTIME_SEQUENCE"):campaign_fixture(sequence_gap=True)
    c=campaign_fixture();object.__setattr__(c.runs[5].runtime_sample.health,"replay_identity","forged")
    with pytest.raises(ValueError):create_runtime_sample(**c.runs[5].runtime_sample.canonical_payload())
    with pytest.raises(TypeError):create_qualification_run(publication_succeeded=True)
    with pytest.raises(ValueError):policy(require_strict_runtime_sequence="yes")
def test_per_run_delivery_conjunction_counts_different_failures():
    c=campaign_fixture();object.__setattr__(c.runs[0].pipeline,"status","FAIL");object.__setattr__(c.runs[1].delivery,"status","FAIL")
    report=validate_delivery_reliability(c);assert report.failed_runs==2 and report.failure_rate==pytest.approx(2/15) and report.status=="FAIL"
def test_duration_active_expiry_and_canonical_times():
    c=campaign_fixture(utc_offset=True);registry=create_registry(c.policy).append(c,appended_at=stamp(20));stats=aggregate_campaign_statistics(registry)
    assert stats.first_observed_at==stamp(0) and registry.active_at(stamp(-1))==() and registry.active_at(stamp(41))==()
    report=build_qualification_report(c,registry,stats,monitor_runtime_stability(c),run_shadow_campaign(c),validate_delivery_reliability(c),assessed_at=stamp(41));assert report.status=="FAIL"
    with pytest.raises(ValueError):campaign_fixture(policy_value=policy(minimum_campaign_duration_seconds=15))
def test_registry_statistics_and_report_integrity_fail_closed():
    c=campaign_fixture();registry=create_registry(c.policy).append(c,appended_at=stamp(20))
    with pytest.raises(ValueError):registry.append(c,appended_at=stamp(21))
    with pytest.raises(ValueError):replace(registry,previous_registry_identity="broken")
    stats=aggregate_campaign_statistics(registry);runtime=monitor_runtime_stability(c);object.__setattr__(runtime,"campaign_identity","other")
    report=build_qualification_report(c,registry,stats,runtime,run_shadow_campaign(c),validate_delivery_reliability(c),assessed_at=stamp(20));assert report.status=="FAIL" and report.operational_recommendation=="NOT READY"
def test_recommendation_requires_policy_consecutive_campaign_threshold():
    c=campaign_fixture(policy_value=policy(required_consecutive_stable_campaigns=2));report,_,_=complete(c,stamp(20));assert report.status=="FAIL" and report.operational_recommendation=="CONDITIONALLY READY"
