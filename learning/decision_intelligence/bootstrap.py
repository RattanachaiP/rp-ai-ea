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
        """Refuse the retired construct-and-activate shortcut.

        Construction remains available through the engine.  Production activation
        is now exclusively an explicit invocation of ``operator_activation`` with
        caller-selected identities and owner authority.
        """
        raise DecisionIntelligenceError("ACTIVATION_REQUIRES_OPERATOR_COMMAND")
