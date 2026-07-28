"""PR266 operational qualification, drift, lineage and authority tests."""
from datetime import datetime,timedelta,timezone
from dataclasses import replace

from bridge.v28.campaign_statistics import aggregate_campaign_statistics
from bridge.v28.delivery_reliability_validator import validate_delivery_reliability
from bridge.v28.qualification_campaign import create_qualification_campaign,create_qualification_run
from bridge.v28.qualification_registry import QualificationRegistry
from bridge.v28.qualification_report import build_qualification_report
from bridge.v28.runtime_stability_monitor import monitor_runtime_stability
from bridge.v28.shadow_campaign_runner import run_shadow_campaign
from tests.test_v28_end_to_end_validation import reports
from bridge.v28.certification_report import build_certification_report

BASE=datetime(1970,1,1,0,1,40,tzinfo=timezone.utc)
def stamp(n):return (BASE+timedelta(seconds=n)).isoformat().replace("+00:00","Z")
def certification():
    values=reports();return build_certification_report(*values)
def campaign(*,bad_delivery=False,recovery=False,lineage=None):
    cert=certification();runs=[]
    for ordinal,action in enumerate(("BUY","SELL","HOLD","BUY","SELL","HOLD"),1):
        runs.append(create_qualification_run(ordinal=ordinal,action=action,observed_at=stamp(ordinal),certification=cert,runtime_health_identity="stable-health",publication_succeeded=not (bad_delivery and ordinal==6),validation_succeeded=True,delivery_succeeded=True,recovery_attempted=recovery and ordinal==6))
    return create_qualification_campaign(lineage_identity=lineage,started_at=stamp(0),expires_at=stamp(10),runs=runs)

def test_long_campaign_qualifies_only_for_human_review():
    c=campaign();runtime=monitor_runtime_stability(c,maximum_heartbeat_gap_seconds=2);shadow=run_shadow_campaign(c);delivery=validate_delivery_reliability(c);stats=aggregate_campaign_statistics(c)
    report=build_qualification_report(c,stats,runtime,shadow,delivery,assessed_at=stamp(10))
    assert runtime.status==shadow.status==delivery.status==report.status=="PASS"
    assert report.operational_recommendation=="READY FOR HUMAN REVIEW"
    assert report.production_authorized is False and '"production_authorized":false' in report.to_json()

def test_delivery_failure_and_recovery_fail_closed():
    c=campaign(bad_delivery=True,recovery=True);delivery=validate_delivery_reliability(c)
    assert delivery.status=="FAIL" and delivery.failure_rate>0
    assert "AUTOMATIC_RECOVERY_FORBIDDEN" in delivery.reasons

def test_replay_and_certification_drift_fail_closed():
    c=campaign();bad=replace(c.runs[-1])
    # This models corrupt evidence bypassing constructors: monitor must still reject it.
    object.__setattr__(bad.certification,"status","FAIL")
    object.__setattr__(c,"runs",c.runs[:-1]+(bad,))
    assert monitor_runtime_stability(c,maximum_heartbeat_gap_seconds=2).status=="FAIL"
    assert run_shadow_campaign(c).status=="FAIL"

def test_registry_is_append_only_lineaged_and_expiry_is_explicit():
    first=campaign();second=campaign(lineage=first.campaign_identity)
    registry=QualificationRegistry().append(first).append(second)
    assert len(registry.campaigns)==2 and not registry.active_at(stamp(10))
    try: QualificationRegistry().append(second)
    except ValueError as exc: assert "LINEAGE" in str(exc)
    else: raise AssertionError("unlineaged campaign accepted")
