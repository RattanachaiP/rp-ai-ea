"""Explicit demo/replay/validation controller; production promotion is impossible."""
from dataclasses import dataclass
from .execution_bridge import ExecutionBridge, BridgeResult
from .execution_replay_validator import validate_execution_replay
from .shadow_executor import ShadowExecutor


@dataclass(frozen=True)
class DemoRuntimeResult:
    mode: str; completed: bool; result: object


class DemoRuntimeController:
    MODES = frozenset({"SHADOW", "REPLAY", "VALIDATION", "DEMO"})
    def __init__(self, executor=None, shadow_executor=None):
        self._executor = executor; self._shadow = shadow_executor or ShadowExecutor()
    def run(self, mode, plan, contract, health, broker, publication, *, human_approved=False, demo_environment=False):
        if mode not in self.MODES: raise ValueError("PRODUCTION_MODE_NOT_AUTHORIZED")
        validation = validate_execution_replay(plan, contract, health, broker, publication)
        if mode in {"REPLAY", "VALIDATION"}: return DemoRuntimeResult(mode, validation.valid, validation)
        if mode == "SHADOW": return DemoRuntimeResult(mode, validation.valid, self._shadow.execute(plan) if validation.valid else validation)
        if not demo_environment: return DemoRuntimeResult(mode, False, BridgeResult(False, "DEMO_ENVIRONMENT_REQUIRED"))
        if self._executor is None: return DemoRuntimeResult(mode, False, BridgeResult(False, "EXECUTOR_UNAVAILABLE"))
        delivered = ExecutionBridge(self._executor).deliver(plan, contract, health, broker, publication, demo_approved=human_approved)
        return DemoRuntimeResult(mode, delivered.delivered, delivered)
