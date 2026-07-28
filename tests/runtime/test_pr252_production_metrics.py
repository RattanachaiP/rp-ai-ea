import json

import pytest

from runtime.production_metrics import ProductionMetrics, SCHEMA_VERSION


def read(root, name):
    return json.loads((root / name).read_text(encoding="utf-8"))


def test_writes_complete_metrics_and_daily_summary_atomically(tmp_path):
    now = [1_785_196_800.0]
    metrics = ProductionMetrics(tmp_path, clock=lambda: now[0])
    now[0] += 2.5
    metrics.decision_published({"decision_uuid": "decision-1"}, decision_latency_ms=12.0,
                               json_publish_latency_ms=2.0)
    metrics.execution_result(decision_to_execution_latency_ms=30.0,
                             mt5_execution_latency_ms=18.0,
                             spread_at_entry_points=2.5, slippage_points=-0.2,
                             accepted=True)
    metrics.execution_result(decision_to_execution_latency_ms=50.0,
                             mt5_execution_latency_ms=25.0,
                             spread_at_entry_points=None, slippage_points=None,
                             accepted=False, rejection_reason="MARKET_CLOSED")
    metrics.duplicate_decision()
    metrics.runtime_exception(owner="PUBLISHER", reason="PUBLICATION_FAILED")

    document = read(tmp_path, "runtime_metrics.json")
    assert document["schema_version"] == SCHEMA_VERSION
    assert document["runtime_uptime_seconds"] == 2.5
    assert document["runtime_restart_count"] == 0
    assert document["decision_latency_ms"]["average"] == 12.0
    assert document["decision_to_execution_latency_ms"]["average"] == 40.0
    assert document["json_publish_latency_ms"]["average"] == 2.0
    assert document["mt5_execution_latency_ms"]["maximum"] == 25.0
    assert document["spread_at_entry_points"]["count"] == 1
    assert document["slippage_points"]["minimum"] == -0.2
    assert document["execution_rejection_reasons"] == {"MARKET_CLOSED": 1}
    assert document["duplicate_decision_count"] == 1
    assert document["runtime_exception_count"] == 1
    summary = read(tmp_path, "runtime_daily_summary.json")
    assert summary["summary_date_utc"] == "2026-07-28"
    assert summary["execution_rejection_count"] == 1
    assert not tuple(tmp_path.glob("*.tmp"))


def test_restart_count_survives_process_lifecycle(tmp_path):
    ProductionMetrics(tmp_path, clock=lambda: 1_785_196_800.0)
    restarted = ProductionMetrics(tmp_path, clock=lambda: 1_785_196_900.0)
    assert restarted.snapshot()["runtime_restart_count"] == 1


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), "slow"])
def test_invalid_latency_is_rejected_without_replacing_evidence(tmp_path, value):
    metrics = ProductionMetrics(tmp_path, clock=lambda: 1_785_196_800.0)
    before = (tmp_path / "runtime_metrics.json").read_bytes()
    with pytest.raises(ValueError, match="INVALID_METRIC"):
        metrics.decision_published({}, decision_latency_ms=value)
    assert (tmp_path / "runtime_metrics.json").read_bytes() == before


def test_rejection_reason_contract_is_unambiguous(tmp_path):
    metrics = ProductionMetrics(tmp_path, clock=lambda: 1_785_196_800.0)
    common = dict(decision_to_execution_latency_ms=1, mt5_execution_latency_ms=1,
                  spread_at_entry_points=None, slippage_points=None)
    with pytest.raises(ValueError, match="REJECTED_EXECUTION_REQUIRES_REASON"):
        metrics.execution_result(**common, accepted=False)
    with pytest.raises(ValueError, match="ACCEPTED_EXECUTION_HAS_REJECTION_REASON"):
        metrics.execution_result(**common, accepted=True, rejection_reason="NONE")
