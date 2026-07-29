"""PR270 governed outcome analytics contract tests."""
from dataclasses import replace

import pytest

from bridge.v28.offline_learning import build_learning_dataset, publish_learning_evidence
from bridge.v28.outcome_analytics import (CalibrationBucket, ErrorClass, OutcomeAnalyticsReport,
                                          analyze_learning_evidence, validate_analytics_replay)
from bridge.v28.outcome_evidence import publish_outcome_evidence
from bridge.v28.outcome_registry import create_outcome_registry
from bridge.v28.pipeline_validator import certification_identity
from tests.test_v28_outcome_intelligence import outcome


def learning_evidence(*records):
    registry = create_outcome_registry()
    for record in records:
        registry = registry.append(record)
    outcome_evidence = publish_outcome_evidence(registry)
    dataset = build_learning_dataset(registry, outcome_evidence)
    return publish_learning_evidence(registry, outcome_evidence, dataset)


def test_complete_analytics_are_deterministic_and_source_bound():
    evidence = learning_evidence(outcome("analytics-one"), outcome("analytics-two"))
    first = analyze_learning_evidence(evidence)
    assert first == analyze_learning_evidence(evidence)
    assert first.source_dataset_identity == evidence.dataset.dataset_identity
    assert first.source_learning_evidence_identity == evidence.evidence_identity
    assert first.expectancy.count == 2
    assert (first.expectancy.wins, first.expectancy.losses, first.expectancy.breakeven) == (2, 0, 0)
    assert first.expectancy.expectancy_r == 2.0
    assert first.drawdown.maximum_net_drawdown == 0
    assert first.regime_performance[0].group == "TREND"
    assert first.opportunity_performance[0].group == "PULLBACK"
    assert first.confidence_calibration[8].observed_win_rate == 1.0
    assert len(first.confidence_calibration) == 10
    assert first.confidence_calibration[-1].upper_bound_inclusive is True
    assert first.error_classification == ()
    assert validate_analytics_replay(evidence, first)


def test_empty_learning_dataset_has_total_zero_analytics():
    report = analyze_learning_evidence(learning_evidence())
    assert report.expectancy.count == 0
    assert report.expectancy.expectancy_r == 0
    assert report.drawdown.maximum_r_drawdown == 0
    assert report.regime_performance == report.opportunity_performance == ()
    assert sum(bucket.count for bucket in report.confidence_calibration) == 0
    assert report.error_classification == ()


def test_report_explicitly_has_no_learning_candidate_or_runtime_authority():
    report = analyze_learning_evidence(learning_evidence(outcome()))
    assert report.analytics_only is True
    assert report.training_performed is False
    assert report.candidates_generated is False
    assert report.runtime_mutated is False
    assert report.production_authorized is False
    with pytest.raises(ValueError, match="AUTHORITY"):
        replace(report, training_performed=True)


def test_report_is_content_addressed_and_tampering_fails_replay():
    evidence = learning_evidence(outcome())
    report = analyze_learning_evidence(evidence)
    object.__setattr__(report, "source_dataset_identity", "forged")
    assert not validate_analytics_replay(evidence, report)


def test_replay_rejects_another_learning_evidence_source():
    first_evidence = learning_evidence(outcome("first"))
    second_evidence = learning_evidence(outcome("second"))
    assert not validate_analytics_replay(second_evidence, analyze_learning_evidence(first_evidence))


def test_summary_inconsistency_is_rejected_even_with_recomputed_identity():
    report = analyze_learning_evidence(learning_evidence(outcome()))
    values = report.canonical_payload() | {
        "win_loss_distribution": replace(report.win_loss_distribution,
                                         total_net_profit=1.0, mean_net_profit=1.0)
    }
    with pytest.raises(ValueError, match="SUMMARY_MISMATCH"):
        OutcomeAnalyticsReport(**values, report_identity=certification_identity(
            "V28_ANALYTICS_REPORT", values))


def test_forged_snapshot_lineage_and_source_order_are_rejected():
    report = analyze_learning_evidence(learning_evidence(outcome("one"), outcome("two")))
    with pytest.raises(ValueError, match="LINEAGE"):
        replace(report, source_dataset_version_identity="forged")
    with pytest.raises(ValueError, match="LINEAGE"):
        replace(report, source_outcome_identities=tuple(reversed(report.source_outcome_identities)))


def test_performance_arithmetic_drawdown_and_non_finite_values_are_rejected():
    report = analyze_learning_evidence(learning_evidence(outcome()))
    with pytest.raises(ValueError, match="SUMMARY_ARITHMETIC"):
        replace(report.expectancy, mean_net_profit=1.0)
    with pytest.raises(ValueError, match="NUMERIC"):
        replace(report.expectancy, total_net_profit=float("nan"))
    with pytest.raises(ValueError, match="DRAWDOWN_TOTAL"):
        replace(report, drawdown=replace(report.drawdown, ending_cumulative_net=1.0))


def test_duplicate_or_noncanonical_groups_are_rejected():
    report = analyze_learning_evidence(learning_evidence(outcome()))
    duplicate = report.regime_performance + report.regime_performance
    with pytest.raises(ValueError, match="REGIME_GROUP_ORDER"):
        replace(report, regime_performance=duplicate)
    with pytest.raises(ValueError, match="OPPORTUNITY_GROUP_ORDER"):
        replace(report, opportunity_performance=tuple(reversed(report.opportunity_performance)) * 2)


def test_calibration_arithmetic_count_order_overlap_and_one_boundary_are_enforced():
    report = analyze_learning_evidence(learning_evidence(outcome()))
    bucket = report.confidence_calibration[8]
    with pytest.raises(ValueError, match="CALIBRATION_ARITHMETIC"):
        replace(bucket, absolute_error=0.0)
    with pytest.raises(ValueError, match="CALIBRATION_COUNT"):
        replace(report, confidence_calibration=tuple(
            replace(item, count=0, confidence_sum=0.0, observed_wins=0,
                    mean_confidence=0.0, observed_win_rate=0.0, absolute_error=0.0)
            if index == 8 else item
            for index, item in enumerate(report.confidence_calibration)))
    with pytest.raises(ValueError, match="CALIBRATION_ORDER"):
        replace(report, confidence_calibration=tuple(reversed(report.confidence_calibration)))
    assert report.confidence_calibration[-1].upper_bound == 1.0
    assert report.confidence_calibration[-1].upper_bound_inclusive


def test_error_classes_cannot_add_duplicate_unknown_or_unproven_losses():
    report = analyze_learning_evidence(learning_evidence(outcome()))
    unknown = ErrorClass("FORGED", 1, ("unknown-outcome",))
    with pytest.raises(ValueError, match="ERROR_LINEAGE"):
        replace(report, error_classification=(unknown,))
    with pytest.raises(ValueError, match="ERROR_LINEAGE"):
        replace(report, losing_outcome_identities=(report.source_outcome_identities[0],))
    with pytest.raises(ValueError, match="ERROR_CLASS"):
        ErrorClass("FORGED", 2, (report.source_outcome_identities[0],) * 2)
