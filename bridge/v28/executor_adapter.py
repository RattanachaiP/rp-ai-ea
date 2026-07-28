"""Backward-compatible projection into the existing V27 Executor interface."""
from bridge.decision_writer import WriterReadResult
from .executor_contract import ExecutorContract
from .execution_plan import identity


def adapt_executor_contract(contract: ExecutorContract) -> WriterReadResult:
    if contract.replay_identity != identity("V28_EXECUTOR_CONTRACT_REPLAY", contract.canonical_payload()):
        return WriterReadResult({}, False, False, "EXECUTOR_CONTRACT_INVALID")
    payload = {"sequence_id": contract.runtime_sequence_id, "decision": contract.direction,
               "direction": contract.direction, "entry_permission": True, "entry_state": "ENTRY_ALLOWED",
               "construction_action": "ALLOW_START", "fail_safe": False, "executable": True,
               "symbol": contract.symbol, "volume": contract.approved_volume,
               "entry_price": contract.executable_entry_price, "stop_loss": contract.protective_stop,
               "take_profit": contract.target}
    return WriterReadResult(payload, True, False, None)

