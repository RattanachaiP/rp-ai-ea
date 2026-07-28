"""Produce categorical confidence from the governed statistical evidence assessment."""
from .decision_contract import Confidence


def build_confidence(expectancy, evidence):
    sufficient = expectancy.status == "POSITIVE_EXPECTANCY"
    basis = ("VERIFIED_EVIDENCE_IDENTITY", "POSITIVE_LOWER_CONFIDENCE_BOUND",
             "SUPPORTED_OUT_OF_SAMPLE_METHOD", "CURRENT_SCOPE_MATCH") if sufficient else expectancy.conflicting_evidence
    return Confidence("GOVERNED_EVIDENCE_SUFFICIENT" if sufficient else "GOVERNED_EVIDENCE_INSUFFICIENT",
                      evidence.confidence_measure if sufficient else None, basis,
                      "categorical assessment of governed statistical evidence; no factor averaging", sufficient)
