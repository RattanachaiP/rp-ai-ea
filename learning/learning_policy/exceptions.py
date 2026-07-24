"""Errors raised by the governed learning-policy boundary."""


class GovernedLearningPolicyError(ValueError):
    """The supplied attribution evidence cannot safely be policy evaluated."""
