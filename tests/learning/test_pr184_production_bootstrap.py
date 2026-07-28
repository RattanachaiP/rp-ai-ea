from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[2]))

import pytest

from learning.decision_intelligence import GovernedDecisionIntelligenceBootstrap
from test_pr184_decision_intelligence import setup_engine


def test_bootstrap_cannot_construct_or_infer_an_activation(tmp_path):
    context_report, _, engine = setup_engine(tmp_path)
    bootstrap = GovernedDecisionIntelligenceBootstrap(engine)

    with pytest.raises(Exception, match="ACTIVATION_REQUIRES_OPERATOR_COMMAND"):
        bootstrap.run(context_report)
    assert engine.repository.activations() == ()
