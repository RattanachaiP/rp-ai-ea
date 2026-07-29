"""Independent deterministic evaluator; never imports or invokes Training or Runtime."""
from math import sqrt
from .identity import identity_for
from .models import (DIMENSIONS, DimensionResult, EvaluationDataset, EvaluationPolicy, EvaluationReport,
                     ReplayValidation, StatisticalValidation, qualification)
from learning.common.immutable import thaw
from bridge.v28.outcome_analytics import validate_analytics_replay

def _validate(obj): type(obj)(**obj.__dict__)

class ModelEvaluator:
    def __init__(self, policy: EvaluationPolicy): _validate(policy); self.policy = policy

    def _statistics(self, prediction, dataset):
        labels = tuple(x.label for x in dataset.rows); errors = tuple(prediction-x for x in labels); count = len(errors)
        error_sum = sum(errors); squared_sum = sum(x*x for x in errors); mean = error_sum/count
        mae = sum(abs(x) for x in errors)/count; mse = squared_sum/count
        std = sqrt(sum((x-mean)**2 for x in errors)/count)
        brier = sum((x.confidence-(1. if x.label > 0 else 0.))**2 for x in dataset.rows)/count
        regimes = {key: sum(x.regime_identity == key for x in dataset.rows) for key in sorted({x.regime_identity for x in dataset.rows})}
        return StatisticalValidation(count, error_sum, squared_sum, mean, mae, mse, std, brier, regimes)

    def _computation(self, candidate, dataset):
        stats = self._statistics(candidate.model_artifact["prediction"], dataset)
        predictive = max(0., 1.-stats.mean_squared_error/self.policy.maximum_mse)
        # Generalization is exclusively out-of-training evaluation data; no split or training metric is consulted.
        generalization = predictive
        stability = 1./(1.+stats.error_stddev); calibration = 1./(1.+abs(stats.mean_error))
        downside = sum(max(0., -x.label) for x in dataset.rows)/stats.record_count; risk = 1./(1.+downside)
        coverage = min(1., stats.record_count/self.policy.minimum_records)
        confidence = max(0., 1.-stats.confidence_brier_score/self.policy.maximum_confidence_brier_score)
        regime_mses = [sum((candidate.model_artifact["prediction"]-x.label)**2 for x in dataset.rows if x.regime_identity == regime)/count
                       for regime, count in stats.regime_counts.items()]
        regime = min(max(0., 1.-mse/self.policy.maximum_mse) for mse in regime_mses)
        scores = (predictive, generalization, stability, calibration, risk, 0., coverage, confidence, regime)
        payload = {"candidate_identity": candidate.model_identity, "evaluation_dataset_identity": dataset.dataset_identity,
                   "policy_identity": self.policy.policy_identity, "statistics": thaw(stats.__dict__), "scores_without_replay": scores}
        return stats, scores, identity_for("EVALUATION_COMPUTATION", payload)

    def evaluate(self, candidate_registry, candidate, training_evidence, training_learning_registry,
                 training_analytics, training_dataset, evaluation_learning_registry, evaluation_learning_evidence,
                 evaluation_analytics, evaluation_dataset: EvaluationDataset) -> EvaluationReport:
        for obj in (candidate_registry, candidate, training_evidence, training_learning_registry,
                    training_analytics, training_dataset, evaluation_learning_registry, evaluation_learning_evidence,
                    evaluation_analytics, evaluation_dataset): _validate(obj)
        candidate_entries = tuple(x for x in candidate_registry.entries if x.candidate.model_identity == candidate.model_identity)
        if len(candidate_entries) != 1 or candidate_entries[0].evidence.evidence_identity != training_evidence.evidence_identity:
            raise ValueError("EVALUATION_CANDIDATE_REGISTRY_BINDING_INVALID")
        lineage = candidate.lineage
        evidence_entries = tuple(x for x in training_learning_registry.entries
            if x.evidence.evidence_identity == lineage.source_learning_evidence_identity)
        if (len(evidence_entries) != 1 or training_evidence.evidence_identity != candidate_entries[0].evidence.evidence_identity
                or training_evidence.candidate_identity != candidate.model_identity
                or training_evidence.lineage_identity != lineage.lineage_identity):
            raise ValueError("EVALUATION_TRAINING_LINEAGE_INVALID")
        source_learning_evidence = evidence_entries[0].evidence
        if (training_learning_registry.registry_identity != lineage.source_learning_registry_identity
                or source_learning_evidence.evidence_identity != lineage.source_learning_evidence_identity
                or training_analytics.report_identity != lineage.source_analytics_identity
                or training_analytics.source_learning_evidence_identity != source_learning_evidence.evidence_identity
                or training_dataset.dataset_identity != lineage.dataset_identity
                or training_dataset.source_learning_evidence_identity != source_learning_evidence.evidence_identity
                or training_dataset.source_learning_registry_identity != training_learning_registry.registry_identity
                or training_dataset.source_analytics_identity != training_analytics.report_identity
                or tuple(x.row_identity for x in training_dataset.rows) != candidate.metadata.training_row_identities):
            raise ValueError("EVALUATION_TRAINING_LINEAGE_INVALID")
        if evaluation_dataset.non_overlap_proof.training_row_identities != candidate.metadata.training_row_identities:
            raise ValueError("EVALUATION_NON_OVERLAP_PROOF_BINDING_INVALID")
        evaluation_entries = tuple(x for x in evaluation_learning_registry.entries
            if x.evidence.evidence_identity == evaluation_learning_evidence.evidence_identity)
        if len(evaluation_entries) != 1:
            raise ValueError("EVALUATION_EVIDENCE_NOT_REGISTERED")
        if not validate_analytics_replay(evaluation_learning_evidence, evaluation_analytics):
            raise ValueError("EVALUATION_ANALYTICS_REPLAY_INVALID")
        source = evaluation_learning_evidence.dataset
        if (evaluation_dataset.source_learning_registry_identity != evaluation_learning_registry.registry_identity
                or evaluation_dataset.source_learning_evidence_identity != evaluation_learning_evidence.evidence_identity
                or evaluation_dataset.source_analytics_identity != evaluation_analytics.report_identity
                or evaluation_dataset.source_dataset_identity != source.dataset_identity
                or evaluation_dataset.source_dataset_version_identity != source.dataset_version_identity
                or tuple(x.example_identity for x in evaluation_dataset.rows) != tuple(x.example_identity for x in source.examples)
                or tuple(x.outcome_identity for x in evaluation_dataset.rows) != source.source_outcome_identities):
            raise ValueError("EVALUATION_DATASET_PROVENANCE_INVALID")
        first_stats, first_scores, first_digest = self._computation(candidate, evaluation_dataset)
        second_stats, second_scores, second_digest = self._computation(candidate, evaluation_dataset)
        replay = ReplayValidation(first_digest, second_digest, first_digest == second_digest and first_stats == second_stats and first_scores == second_scores)
        scores = first_scores[:5] + (1. if replay.consistent else 0.,) + first_scores[6:]
        dims = tuple(DimensionResult(name, score, self.policy.minimum_dimension_score,
            score >= self.policy.minimum_dimension_score, {"evaluation_dataset_identity": evaluation_dataset.dataset_identity,
            "record_count": first_stats.record_count}) for name, score in zip(DIMENSIONS, scores))
        qualified, reasons = qualification(self.policy, first_stats, dims)
        return EvaluationReport(candidate.model_identity, candidate_registry.registry_identity, training_evidence.evidence_identity,
            training_learning_registry.registry_identity, training_analytics.report_identity, training_dataset.dataset_identity,
            evaluation_dataset.dataset_identity, evaluation_dataset.dataset_version, self.policy, dims,
            sum(scores)/len(scores), qualified, reasons, first_stats, replay)

    def replay(self, expected, *inputs):
        try: _validate(expected); return self.evaluate(*inputs) == expected
        except (TypeError, ValueError, AttributeError): return False
