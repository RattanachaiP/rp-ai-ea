"""Append-only authoritative compliance evidence registry."""
from dataclasses import dataclass
from .candidate import DOMAINS, QualificationAttestation
from .identity import identity_for

@dataclass(frozen=True)
class QualificationEvidenceIssuer:
    domain: str; issuer_reference: str; issuer_identity: str = ""
    def __post_init__(self):
        if self.domain not in DOMAINS or not isinstance(self.issuer_reference, str) or not self.issuer_reference.strip():
            raise ValueError("QUALIFICATION_EVIDENCE_ISSUER_INVALID")
        expected = identity_for("QUALIFICATION_EVIDENCE_ISSUER", {"domain": self.domain, "issuer_reference": self.issuer_reference})
        if self.issuer_identity and self.issuer_identity != expected: raise ValueError("QUALIFICATION_EVIDENCE_ISSUER_IDENTITY_INVALID")
        object.__setattr__(self, "issuer_identity", expected)
    def issue(self, candidate_identity, evaluation_report_identity, qualification_policy_identity, compliant, authority_reference):
        return QualificationAttestation(self.domain, candidate_identity, evaluation_report_identity,
            qualification_policy_identity, compliant, self.issuer_identity, authority_reference)

@dataclass(frozen=True)
class QualificationEvidenceRegistry:
    attestations: tuple[QualificationAttestation, ...] = (); registry_identity: str = ""
    def __post_init__(self):
        values = tuple(self.attestations); object.__setattr__(self, "attestations", values)
        for value in values: QualificationAttestation(**value.__dict__)
        keys = tuple((x.domain, x.candidate_identity, x.evaluation_report_identity, x.qualification_policy_identity) for x in values)
        if len(keys) != len(set(keys)): raise ValueError("DUPLICATE_QUALIFICATION_ATTESTATION")
        expected = identity_for("QUALIFICATION_EVIDENCE_REGISTRY", {"attestation_identities": tuple(x.attestation_identity for x in values)})
        if self.registry_identity and self.registry_identity != expected: raise ValueError("QUALIFICATION_EVIDENCE_REGISTRY_IDENTITY_INVALID")
        object.__setattr__(self, "registry_identity", expected)
    def append(self, attestation): return QualificationEvidenceRegistry(self.attestations + (attestation,))
    def evidence_for(self, candidate_identity, report_identity, policy_identity):
        matches = tuple(x for x in self.attestations if x.candidate_identity == candidate_identity and
                        x.evaluation_report_identity == report_identity and x.qualification_policy_identity == policy_identity)
        if tuple(x.domain for x in matches) != DOMAINS: raise ValueError("QUALIFICATION_AUTHORITATIVE_EVIDENCE_INCOMPLETE")
        from .candidate import QualificationEvidence
        return QualificationEvidence(candidate_identity, report_identity, policy_identity,
                                     tuple(x.attestation_identity for x in matches), self.registry_identity)
