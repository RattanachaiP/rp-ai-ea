"""PR269 offline learning foundation contract tests."""
from dataclasses import replace

import pytest

from bridge.v28.offline_learning import (build_learning_dataset, create_learning_registry,
                                         publish_learning_evidence, validate_dataset_replay)
from bridge.v28.outcome_evidence import publish_outcome_evidence
from bridge.v28.outcome_registry import create_outcome_registry
from tests.test_v28_outcome_intelligence import outcome


def sources(*records):
    registry = create_outcome_registry()
    for record in records:
        registry = registry.append(record)
    return registry, publish_outcome_evidence(registry)


def test_dataset_is_complete_deterministic_and_outcome_registry_bound():
    registry, evidence = sources(outcome("learning-trade"))
    first = build_learning_dataset(registry, evidence)
    second = build_learning_dataset(registry, evidence)
    assert first == second
    assert first.source_outcome_registry_identity == registry.registry_identity
    row = first.examples[0]
    assert row.features.regime["state"] == "TREND"
    assert row.features.opportunity["archetype"] == "PULLBACK"
    assert row.features.confidence == .8
    assert row.label.expectancy_evidence["r_multiple"] == 2.0
    assert (row.label.holding_time_seconds, row.label.exit_reason) == (1800, "TAKE_PROFIT")
    assert (row.label.slippage, row.label.spread, row.label.commission) == (.4, .2, -4.0)
    assert validate_dataset_replay(registry, evidence, first)


def test_dataset_and_nested_features_are_immutable_and_tamper_evident():
    registry, evidence = sources(outcome())
    dataset = build_learning_dataset(registry, evidence)
    with pytest.raises(Exception):
        dataset.examples = ()
    with pytest.raises(TypeError):
        dataset.examples[0].features.regime["state"] = "RANGE"
    object.__setattr__(dataset.examples[0].label, "commission", 0.0)
    assert not validate_dataset_replay(registry, evidence, dataset)


def test_mismatched_or_mutated_outcome_authority_fails_closed():
    registry, evidence = sources(outcome("trade-one"))
    other_registry, _ = sources(outcome("trade-two"))
    with pytest.raises(ValueError, match="SOURCE_OUTCOME"):
        build_learning_dataset(other_registry, evidence)
    object.__setattr__(evidence, "record_count", 99)
    with pytest.raises(ValueError, match="OUTCOME_EVIDENCE"):
        build_learning_dataset(registry, evidence)


def test_learning_evidence_is_descriptive_and_has_no_production_authority():
    registry, evidence = sources(outcome())
    dataset = build_learning_dataset(registry, evidence)
    contract = publish_learning_evidence(registry, evidence, dataset)
    assert contract.source_authority == "OUTCOME_REGISTRY_ONLY"
    assert contract.integrity_validated and contract.replay_validated
    assert contract.training_performed is False
    assert contract.production_authorized is False
    assert contract.snapshot.record_count == 1
    with pytest.raises(ValueError, match="CONTRACT_INVALID"):
        replace(contract, training_performed=True, evidence_identity=contract.evidence_identity)


def test_learning_registry_is_append_only_identity_bound_and_versioned():
    outcome_registry, outcome_evidence = sources(outcome())
    dataset = build_learning_dataset(outcome_registry, outcome_evidence)
    contract = publish_learning_evidence(outcome_registry, outcome_evidence, dataset)
    empty = create_learning_registry()
    populated = empty.append(contract)
    assert empty.entries == () and populated.entries == (contract,)
    assert dataset.dataset_version_identity and dataset.dataset_identity
    with pytest.raises(ValueError, match="DUPLICATE_DATASET"):
        populated.append(contract)


def test_registry_order_and_source_content_are_identity_significant():
    one, one_evidence = sources(outcome("one"), outcome("two"))
    two, two_evidence = sources(outcome("two"), outcome("one"))
    dataset_one = build_learning_dataset(one, one_evidence)
    dataset_two = build_learning_dataset(two, two_evidence)
    assert dataset_one.dataset_identity != dataset_two.dataset_identity
    assert dataset_one.dataset_version_identity != dataset_two.dataset_version_identity
