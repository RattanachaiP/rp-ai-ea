"""PR269 offline learning foundation contract tests."""
from dataclasses import replace

import pytest

from bridge.v28.offline_learning import (LearningDataset, LearningEvidenceContract, LearningFeatureSet,
                                         LearningRegistry, LearningSnapshot,
                                         build_learning_dataset, create_learning_registry,
                                         publish_learning_evidence, validate_dataset_replay)
from bridge.v28.outcome_evidence import publish_outcome_evidence
from bridge.v28.outcome_registry import create_outcome_registry
from bridge.v28.pipeline_validator import certification_identity
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
    assert empty.entries == () and populated.entries[0].evidence == contract
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


@pytest.mark.parametrize("field,value", [
    ("confidence", float("nan")), ("confidence", float("inf")),
])
def test_feature_numerics_reject_non_finite_values(field, value):
    registry, evidence = sources(outcome())
    feature = build_learning_dataset(registry, evidence).examples[0].features
    with pytest.raises(ValueError, match="NUMERIC"):
        replace(feature, **{field: value})


@pytest.mark.parametrize("field,value", [
    ("holding_time_seconds", -1.0), ("holding_time_seconds", float("nan")),
    ("spread", -0.1), ("spread", float("inf")), ("slippage", float("nan")),
    ("commission", float("inf")),
])
def test_label_numerics_reject_non_finite_and_invalid_ranges(field, value):
    registry, evidence = sources(outcome())
    label = build_learning_dataset(registry, evidence).examples[0].label
    with pytest.raises(ValueError, match="NUMERIC"):
        replace(label, **{field: value})


def test_example_rejects_mixed_feature_label_source_lineage():
    registry, evidence = sources(outcome())
    example = build_learning_dataset(registry, evidence).examples[0]
    values = example.features.canonical_payload() | {"trade_identity": "another-trade"}
    mixed = LearningFeatureSet(**values, feature_identity=certification_identity("V28_LEARNING_FEATURES", values))
    with pytest.raises(ValueError, match="EXAMPLE_LINEAGE"):
        replace(example, features=mixed)


def test_snapshot_rejects_duplicates_and_contract_rejects_dataset_mismatch():
    registry, evidence = sources(outcome())
    dataset = build_learning_dataset(registry, evidence)
    contract = publish_learning_evidence(registry, evidence, dataset)
    snapshot = contract.snapshot
    duplicate_values = snapshot.canonical_payload() | {
        "example_identities": snapshot.example_identities * 2, "record_count": 2}
    with pytest.raises(ValueError, match="SNAPSHOT_COUNT"):
        LearningSnapshot(**duplicate_values, snapshot_identity=certification_identity(
            "V28_LEARNING_SNAPSHOT", duplicate_values))
    mismatch_values = snapshot.canonical_payload() | {"dataset_version_identity": "forged-version"}
    mismatch = LearningSnapshot(**mismatch_values, snapshot_identity=certification_identity(
        "V28_LEARNING_SNAPSHOT", mismatch_values))
    evidence_values = contract.canonical_payload() | {"snapshot": mismatch}
    with pytest.raises(ValueError, match="CONTRACT_INVALID"):
        LearningEvidenceContract(**evidence_values, evidence_identity=certification_identity(
            "V28_LEARNING_EVIDENCE", evidence_values))


def test_registry_rejects_forged_ancestry_and_dataset_replay_reordering():
    first_source, first_evidence = sources(outcome("ancestry-one"))
    second_source, second_evidence = sources(outcome("ancestry-two"))
    first_contract = publish_learning_evidence(first_source, first_evidence,
                                               build_learning_dataset(first_source, first_evidence))
    second_contract = publish_learning_evidence(second_source, second_evidence,
                                                build_learning_dataset(second_source, second_evidence))
    registry = create_learning_registry().append(first_contract).append(second_contract)
    forged_values = registry.canonical_payload() | {"previous_registry_identity": "forged"}
    with pytest.raises(ValueError, match="PREDECESSOR"):
        LearningRegistry(**forged_values, registry_identity=certification_identity(
            "V28_LEARNING_REGISTRY", forged_values))

    source, source_evidence = sources(outcome("replay-one"), outcome("replay-two"))
    dataset = build_learning_dataset(source, source_evidence)
    reordered_values = dataset.canonical_payload() | {
        "examples": tuple(reversed(dataset.examples)),
        "source_outcome_identities": tuple(reversed(dataset.source_outcome_identities)),
    }
    reordered = LearningDataset(**reordered_values, dataset_identity=certification_identity(
        "V28_LEARNING_DATASET", reordered_values))
    assert not validate_dataset_replay(source, source_evidence, reordered)
