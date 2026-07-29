"""Independent deterministic evaluator; deliberately has no training or Runtime dependency."""
from math import sqrt
from .identity import identity_for
from .models import DIMENSIONS, DimensionResult, EvaluationPolicy, EvaluationReport, ReplayValidation, StatisticalValidation

def _validate(obj):
    type(obj)(**obj.__dict__)

class ModelEvaluator:
    def __init__(self, policy: EvaluationPolicy): _validate(policy); self.policy = policy
    def evaluate(self, candidate_registry, candidate, training_evidence, learning_registry, analytics) -> EvaluationReport:
        for obj in (candidate_registry, candidate, training_evidence, learning_registry, analytics): _validate(obj)
        entries = [e for e in candidate_registry.entries if e.candidate.model_identity == candidate.model_identity]
        if len(entries) != 1 or entries[0].evidence.evidence_identity != training_evidence.evidence_identity:
            raise ValueError("EVALUATION_CANDIDATE_REGISTRY_BINDING_INVALID")
        if training_evidence.candidate_identity != candidate.model_identity: raise ValueError("EVALUATION_TRAINING_EVIDENCE_BINDING_INVALID")
        learning_entries = tuple(learning_registry.entries)
        if not learning_entries: raise ValueError("EVALUATION_LEARNING_REGISTRY_EMPTY")
        evidence = learning_entries[-1].evidence
        if analytics.source_learning_evidence_identity != evidence.evidence_identity:
            raise ValueError("EVALUATION_ANALYTICS_BINDING_INVALID")
        examples = tuple(evidence.dataset.examples)
        if tuple(x.outcome_identity for x in examples) != analytics.source_outcome_identities:
            raise ValueError("EVALUATION_DATASET_LINEAGE_INVALID")
        prediction = candidate.model_artifact["prediction"]
        labels = tuple(float(x.label.expectancy_evidence["r_multiple"]) for x in examples); errors = tuple(prediction - x for x in labels)
        count = len(errors); mean = sum(errors) / count; mae = sum(abs(x) for x in errors) / count
        mse = sum(x*x for x in errors) / count; std = sqrt(sum((x-mean)**2 for x in errors) / count)
        stats = StatisticalValidation(count, mean, mae, mse, std)
        quality = max(0., 1. - mse / self.policy.maximum_mse)
        holdout = tuple(x for i, x in enumerate(errors) if i % self.policy.holdout_modulus == self.policy.holdout_modulus-1) or errors
        holdout_mse = sum(x*x for x in holdout) / len(holdout)
        generalization = max(0., 1. - holdout_mse / self.policy.maximum_mse)
        stability = 1. / (1. + std); calibration = 1. / (1. + abs(mean))
        downside = sum(max(0., -x) for x in labels) / count; risk = 1. / (1. + downside)
        coverage = min(1., count / self.policy.minimum_records)
        confidences = tuple(float(x.features.confidence) for x in examples)
        confidence = 1. / (1. + (sum(abs(x - (1. if y > 0 else 0.)) for x, y in zip(confidences, labels)) / len(confidences))) if len(confidences) == count else 0.
        regimes = {}
        for x, error in zip(examples, errors):
            regime_key = identity_for("REGIME", dict(x.features.regime)) if x.features.regime else "UNKNOWN"
            regimes.setdefault(regime_key, []).append(error*error)
        regime = min(max(0., 1. - sum(v)/len(v)/self.policy.maximum_mse) for v in regimes.values())
        scores = (quality, generalization, stability, calibration, risk, 1., coverage, confidence, regime)
        dims = tuple(DimensionResult(name, score, score >= self.policy.minimum_score, {"record_count": count}) for name, score in zip(DIMENSIONS, scores))
        candidate_score = sum(scores) / len(scores); qualified = count >= self.policy.minimum_records and all(x.passed for x in dims)
        reasons = ("ALL_DIMENSIONS_PASSED",) if qualified else tuple(["INSUFFICIENT_RECORDS"] if count < self.policy.minimum_records else []) + tuple("DIMENSION_FAILED:"+x.dimension.upper() for x in dims if not x.passed)
        inputs = {"candidate_registry": candidate_registry.registry_identity, "candidate": candidate.model_identity,
                  "training_evidence": training_evidence.evidence_identity, "learning_registry": learning_registry.registry_identity,
                  "analytics": analytics.report_identity, "policy": self.policy.__dict__}
        input_digest = identity_for("EVALUATION_INPUT", inputs)
        provisional = {"input_digest": input_digest, "scores": scores, "statistics": stats.__dict__, "qualified": qualified, "reasons": reasons}
        replay = ReplayValidation(input_digest, identity_for("EVALUATION_REPLAY", provisional))
        return EvaluationReport(candidate.model_identity, candidate_registry.registry_identity, training_evidence.evidence_identity,
          learning_registry.registry_identity, analytics.report_identity, self.policy.policy_identity, dims, candidate_score,
          qualified, reasons, stats, replay)
    def replay(self, expected, *inputs):
        try: _validate(expected); return self.evaluate(*inputs) == expected
        except (TypeError, ValueError, AttributeError): return False
