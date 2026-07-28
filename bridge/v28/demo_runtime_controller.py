"""Explicit shadow/replay/validation/demo controller; Production is not an ontology value."""
from dataclasses import dataclass
from .execution_bridge import DemoExecutor,ExecutionBridge
from .execution_replay_validator import validate_execution_replay
from .shadow_executor import ShadowExecutor

@dataclass(frozen=True)
class DemoRuntimeResult:
    mode: str; completed: bool; result: object

class DemoRuntimeController:
    MODES=frozenset({"SHADOW","REPLAY","VALIDATION","DEMO"})
    def __init__(self,demo_executor: DemoExecutor|None=None,shadow_executor=None):
        if demo_executor is not None and type(demo_executor) is not DemoExecutor: raise TypeError("DEMO_EXECUTOR_CAPABILITY_REQUIRED")
        self._executor=demo_executor; self._shadow=shadow_executor or ShadowExecutor()
    def run(self,mode,plan,contract,compatibility,health,broker,publication,environment,approval,*,evaluation_time):
        if mode not in self.MODES: raise ValueError("MODE_NOT_AUTHORIZED")
        validation=validate_execution_replay(plan,contract,health,broker,publication,environment,approval,
            evaluation_time=evaluation_time,require_delivery_authority=mode=="DEMO")
        if mode in {"REPLAY","VALIDATION"}: return DemoRuntimeResult(mode,validation.valid,validation)
        if mode=="SHADOW":
            result=self._shadow.execute(plan,publication,recorded_at=evaluation_time) if validation.valid else validation
            return DemoRuntimeResult(mode,validation.valid,result)
        if self._executor is None: return DemoRuntimeResult(mode,False,validation if not validation.valid else "DEMO_EXECUTOR_UNAVAILABLE")
        if not validation.valid: return DemoRuntimeResult(mode,False,validation)
        receipt=ExecutionBridge(self._executor).deliver(plan,contract,compatibility,health,broker,publication,environment,approval,delivered_at=evaluation_time)
        return DemoRuntimeResult(mode,receipt.status=="DELIVERED",receipt)
