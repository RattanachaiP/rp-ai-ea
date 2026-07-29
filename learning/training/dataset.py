"""Strict PR269/PR270 adapter; PR269 Learning Evidence owns all training rows."""
from bridge.v28.offline_learning import LearningEvidenceContract, LearningRegistry
from bridge.v28.outcome_analytics import OutcomeAnalyticsReport, validate_analytics_replay
from .models import TrainingDataset, TrainingRow

class TrainingDatasetLoader:
    def load(self, registry: LearningRegistry, evidence: LearningEvidenceContract,
             analytics: OutcomeAnalyticsReport) -> TrainingDataset:
        try:
            LearningRegistry(**registry.__dict__); LearningEvidenceContract(**evidence.__dict__)
            OutcomeAnalyticsReport(**analytics.__dict__)
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("AUTHORITATIVE_TRAINING_SOURCE_INVALID") from exc
        if not any(entry.evidence == evidence for entry in registry.entries):
            raise ValueError("LEARNING_EVIDENCE_NOT_REGISTERED")
        if not validate_analytics_replay(evidence, analytics):
            raise ValueError("OUTCOME_ANALYTICS_REPLAY_INVALID")
        # Canonical row owner is PR269 evidence.dataset. Registry and analytics are
        # authority/integrity inputs, never additional observations.
        rows = tuple(TrainingRow(i, example.outcome_identity, example.example_identity,
            {"confidence": example.features.confidence, "spread": example.label.spread,
             "slippage": example.label.slippage, "holding_time_seconds": example.label.holding_time_seconds},
            example.label.expectancy_evidence["r_multiple"])
            for i, example in enumerate(evidence.dataset.examples))
        return TrainingDataset(rows, len(rows), registry.registry_identity, evidence.evidence_identity,
            analytics.report_identity, evidence.dataset.dataset_identity, evidence.dataset.dataset_version_identity)
