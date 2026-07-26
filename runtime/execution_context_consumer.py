"""PR194 fail-closed Executor consumer of the published ExecutionContext."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from runtime.execution_contract import ExecutionContext, ExecutionContractError, deserialize_execution_context

MAX_PUBLICATION_BYTES = 1_048_576


class ExecutionContextConsumptionError(RuntimeError):
    """A complete rejection of an ExecutionContext publication."""


@dataclass(frozen=True, slots=True)
class ExecutionContextConsumer:
    """Read only execution_context.json and return its immutable public contract."""

    publication_path: Path
    expected_engine_version: str
    expected_replay_uuid: str

    def __init__(self, publication_path: Path | str, *, expected_engine_version: str,
                 expected_replay_uuid: str) -> None:
        path = Path(publication_path)
        if path.name != "execution_context.json":
            raise ExecutionContextConsumptionError("INVALID_PUBLICATION_PATH")
        object.__setattr__(self, "publication_path", path)
        object.__setattr__(self, "expected_engine_version", expected_engine_version)
        object.__setattr__(self, "expected_replay_uuid", expected_replay_uuid)

    def load(self) -> ExecutionContext:
        """Accept one indivisible publication; every failure returns no context."""
        try:
            payload = self.publication_path.read_bytes()
        except OSError as exc:
            raise ExecutionContextConsumptionError("PUBLICATION_UNAVAILABLE") from exc
        if not payload or len(payload) > MAX_PUBLICATION_BYTES:
            raise ExecutionContextConsumptionError("INVALID_PUBLICATION_SIZE")
        try:
            return deserialize_execution_context(
                payload,
                expected_engine_version=self.expected_engine_version,
                expected_replay_uuid=self.expected_replay_uuid,
            )
        except ExecutionContractError as exc:
            raise ExecutionContextConsumptionError("EXECUTION_CONTEXT_REJECTED") from exc


def load_execution_context(publication_path: Path | str, *, expected_engine_version: str,
                           expected_replay_uuid: str) -> ExecutionContext:
    """Load through a short-lived Executor consumer."""
    return ExecutionContextConsumer(
        publication_path,
        expected_engine_version=expected_engine_version,
        expected_replay_uuid=expected_replay_uuid,
    ).load()
