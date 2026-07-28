"""Append-only snapshots of production-readiness candidate lineage."""
from dataclasses import dataclass

from .pipeline_validator import certification_identity
from .production_readiness_candidate import ProductionReadinessCandidate
from .production_readiness_policy import ProductionReadinessPolicy


@dataclass(frozen=True)
class ProductionReadinessRegistry:
    generation: int
    previous_registry_identity: str | None
    candidates: tuple[ProductionReadinessCandidate, ...]
    policy: ProductionReadinessPolicy
    registry_identity: str

    def canonical_payload(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__ if key != "registry_identity"}

    def __post_init__(self):
        ProductionReadinessPolicy(**self.policy.__dict__)
        if self.generation != len(self.candidates):
            raise ValueError("READINESS_REGISTRY_GENERATION_INVALID")
        if (self.generation == 0) != (self.previous_registry_identity is None):
            raise ValueError("READINESS_REGISTRY_PREDECESSOR_INVALID")
        seen = set()
        for index, candidate in enumerate(self.candidates, 1):
            ProductionReadinessCandidate(**candidate.__dict__)
            previous = None if index == 1 else self.candidates[index - 2].candidate_identity
            if (candidate.generation != index or candidate.previous_candidate_identity != previous or
                    candidate.policy.policy_identity != self.policy.policy_identity or
                    candidate.candidate_identity in seen):
                raise ValueError("READINESS_REGISTRY_LINEAGE_INVALID")
            seen.add(candidate.candidate_identity)
        if self.registry_identity != certification_identity("V28_PRODUCTION_READINESS_REGISTRY", self.canonical_payload()):
            raise ValueError("READINESS_REGISTRY_IDENTITY_INVALID")

    def append(self, candidate: ProductionReadinessCandidate):
        expected = self.candidates[-1].candidate_identity if self.candidates else None
        if candidate.candidate_identity in {item.candidate_identity for item in self.candidates}:
            raise ValueError("READINESS_CANDIDATE_DUPLICATE")
        if candidate.generation != self.generation + 1:
            raise ValueError("READINESS_CANDIDATE_FUTURE_GENERATION")
        if candidate.previous_candidate_identity != expected:
            raise ValueError("READINESS_CANDIDATE_LINEAGE_BROKEN")
        if candidate.policy.policy_identity != self.policy.policy_identity:
            raise ValueError("READINESS_CANDIDATE_POLICY_MISMATCH")
        values = dict(generation=self.generation + 1, previous_registry_identity=self.registry_identity,
                      candidates=self.candidates + (candidate,), policy=self.policy)
        return ProductionReadinessRegistry(
            **values, registry_identity=certification_identity("V28_PRODUCTION_READINESS_REGISTRY", values))


def create_production_readiness_registry(policy: ProductionReadinessPolicy):
    values = dict(generation=0, previous_registry_identity=None, candidates=(), policy=policy)
    return ProductionReadinessRegistry(
        **values, registry_identity=certification_identity("V28_PRODUCTION_READINESS_REGISTRY", values))
