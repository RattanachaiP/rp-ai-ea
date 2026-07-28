"""Build the mandatory human-readable decision explanation."""


def explain_decision(decision, expectancy, precheck, confidence, candidate):
    return (f"{decision}: expectancy={expectancy.status}; risk_precheck={precheck.status}; "
            f"confidence={confidence.assessment}; candidate_authorized={candidate.authorized}; "
            f"evidence_replay={expectancy.evidence_replay_identity}")
