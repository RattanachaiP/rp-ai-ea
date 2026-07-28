"""Describe directional environment without trading semantics."""
from .context_contracts import TrendContext


def describe_trend(snapshot, structure, policy):
    if structure.data_quality != "VALID":
        return TrendContext("UNDETERMINED", {"structure_state": structure.state}, "structure is unavailable", structure.data_quality, policy.policy_id, policy.version)
    state = {"ADVANCING": "UPWARD", "DECLINING": "DOWNWARD"}.get(structure.state, "SIDEWAYS")
    changes = tuple(snapshot.bars[i]["close"] - snapshot.bars[i-1]["close"] for i in range(1, len(snapshot.bars)))
    return TrendContext(state, {"close_changes": changes, "structure_state": structure.state},
                        f"close progression and structure describe {state.lower()} context", "VALID", policy.policy_id, policy.version)
