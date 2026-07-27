from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[2]))

from learning.decision_intelligence import (
    GovernedDecisionIntelligenceBootstrap,
)
from test_pr184_decision_intelligence import setup_engine


def test_bootstrap_creates_exactly_one_activation_and_replay_is_idempotent(tmp_path):
    context_report, _, engine = setup_engine(tmp_path)
    bootstrap = GovernedDecisionIntelligenceBootstrap(engine)

    first = bootstrap.run(context_report)
    activation = engine.repository.activations()[0]
    second = bootstrap.run(context_report)

    assert first.decision_intelligences == second.decision_intelligences
    assert first.snapshot_uuid == second.snapshot_uuid
    assert engine.repository.activations() == (activation,)
    assert activation.intelligence_uuid == first.decision_intelligences[0].intelligence_uuid
    assert activation.snapshot_uuid == first.snapshot_uuid
