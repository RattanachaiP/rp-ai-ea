"""Production bootstrap for the canonical PR184 activation boundary."""

from .engine import GovernedDecisionIntelligenceEngine
from .exceptions import DecisionIntelligenceError


class GovernedDecisionIntelligenceBootstrap:
    """Construct PR184 state and establish its sole production activation.

    ``GovernedDecisionIntelligenceEngine`` remains construction-only.  This
    explicit composition owns the separate activation step required before
    Production Startup may consume PR184 state.
    """

    def __init__(self, engine):
        if type(engine) is not GovernedDecisionIntelligenceEngine:
            raise DecisionIntelligenceError("INVALID_DECISION_INTELLIGENCE_ENGINE")
        self.engine = engine

    def run(self, context_report):
        report = self.engine.run(context_report)
        repository = self.engine.repository

        if len(report.decision_intelligences) != 1:
            raise DecisionIntelligenceError(
                "DECISION_INTELLIGENCE_ACTIVATION_SELECTION_AMBIGUOUS"
            )
        intelligence = report.decision_intelligences[0]
        snapshot = repository.latest_snapshot()
        if (
            snapshot is None
            or snapshot.snapshot_uuid != report.snapshot_uuid
            or snapshot.snapshot_digest != report.snapshot_digest
        ):
            raise DecisionIntelligenceError("SNAPSHOT_MISMATCH")

        # activate() is the canonical, idempotent repository boundary.  Calling
        # it for both the first bootstrap and a replay also verifies that an
        # existing activation selects this exact record and snapshot.
        activation = repository.activate(intelligence, snapshot)
        activations = repository.activations()
        if activations != (activation,):
            raise DecisionIntelligenceError(
                "DECISION_INTELLIGENCE_ACTIVATION_AMBIGUOUS"
            )
        return report
