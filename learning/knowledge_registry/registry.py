"""Canonical PR178-to-PR179 admission mapping (not runtime activation)."""


def admission_result(promotion_state):
    if promotion_state == "POLICY_CRITERIA_MET":
        return "REGISTERED", ("PROMOTION_POLICY_CRITERIA_MET", "ADVISORY_ONLY")
    if promotion_state == "INSUFFICIENT_PROMOTION_EVIDENCE":
        return "NOT_ADMITTED", ("INSUFFICIENT_PROMOTION_EVIDENCE", "ADVISORY_ONLY")
    if promotion_state == "REJECTED":
        return "REJECTED", ("PROMOTION_REJECTED", "ADVISORY_ONLY")
    raise ValueError("INVALID_PROMOTION_STATE")
