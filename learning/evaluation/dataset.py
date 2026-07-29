"""Build an evaluation-owned dataset without importing or invoking Training."""
from bridge.v28.offline_learning import LearningEvidenceContract, LearningRegistry
from bridge.v28.outcome_analytics import OutcomeAnalyticsReport, validate_analytics_replay
from .identity import identity_for
from .models import DatasetNonOverlapProof, EvaluationDataset, EvaluationRow

class EvaluationDatasetLoader:
    def load(self, registry: LearningRegistry, evidence: LearningEvidenceContract,
             analytics: OutcomeAnalyticsReport, training_dataset) -> EvaluationDataset:
        try:
            LearningRegistry(**registry.__dict__); LearningEvidenceContract(**evidence.__dict__)
            OutcomeAnalyticsReport(**analytics.__dict__); type(training_dataset)(**training_dataset.__dict__)
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("AUTHORITATIVE_EVALUATION_SOURCE_INVALID") from exc
        matches = tuple(x for x in registry.entries if x.evidence.evidence_identity == evidence.evidence_identity)
        if len(matches) != 1: raise ValueError("EVALUATION_EVIDENCE_NOT_REGISTERED")
        if not validate_analytics_replay(evidence, analytics): raise ValueError("EVALUATION_ANALYTICS_REPLAY_INVALID")
        training_examples = tuple(x.example_identity for x in training_dataset.rows)
        evaluation_examples = tuple(x.example_identity for x in evidence.dataset.examples)
        proof = DatasetNonOverlapProof(tuple(x.row_identity for x in training_dataset.rows), training_examples,
                                       evaluation_examples, len(set(training_examples) & set(evaluation_examples)))
        rows = tuple(EvaluationRow(i, example.outcome_identity, example.example_identity,
            example.label.expectancy_evidence["r_multiple"], example.features.confidence,
            identity_for("REGIME", dict(example.features.regime)) if example.features.regime else "UNKNOWN",
            example.example_identity) for i, example in enumerate(evidence.dataset.examples))
        return EvaluationDataset(rows, registry.registry_identity, evidence.evidence_identity, analytics.report_identity,
            evidence.dataset.dataset_identity, evidence.dataset.dataset_version_identity, proof)
