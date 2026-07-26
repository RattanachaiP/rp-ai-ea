"""PR193 fail-closed publication of the PR192 execution contract.

The publisher is intentionally a narrow production boundary.  It stamps and
constructs the already-frozen contract, verifies its canonical representation,
and atomically replaces ``execution_context.json``.  It does not interpret any
of the execution metadata it is given.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import uuid4

from runtime.execution_contract import (
    CONTRACT_VERSION,
    REQUIRED_FIELDS,
    ExecutionContext,
    deserialize_execution_context,
    serialize_execution_context,
)


PUBLICATION_VERSION = "PR193-EXECUTION-CONTEXT-PUBLICATION.1"
_RUNTIME_FIELDS = REQUIRED_FIELDS - {"timestamp", "contract_version", "payload_digest"}


class ExecutionContextPublicationError(RuntimeError):
    """A publication failure after which no new payload has been published."""


class ExecutionContextPublisher:
    """Atomically publish complete, canonical ``ExecutionContext`` values."""

    def __init__(
        self,
        output_path: Path | str,
        *,
        expected_engine_version: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.output_path = Path(output_path)
        if self.output_path.name != "execution_context.json":
            raise ExecutionContextPublicationError("INVALID_PUBLICATION_PATH")
        if not isinstance(expected_engine_version, str) or not expected_engine_version:
            raise ExecutionContextPublicationError("INVALID_ENGINE_VERSION")
        self.expected_engine_version = expected_engine_version
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create_and_publish(self, values: Mapping[str, Any]) -> ExecutionContext:
        """Timestamp, version, digest, validate, and publish runtime fields.

        ``values`` must contain exactly the schema fields owned by V26.  PR193
        alone supplies the timestamp and frozen PR192 contract version; the
        PR192 constructor supplies the payload digest.
        """
        if not isinstance(values, Mapping) or set(values) != _RUNTIME_FIELDS:
            raise ExecutionContextPublicationError("INVALID_PUBLICATION_FIELDS")
        try:
            timestamp = self._timestamp()
            context = ExecutionContext.create(
                **dict(values), timestamp=timestamp, contract_version=CONTRACT_VERSION
            )
        except Exception as exc:
            raise ExecutionContextPublicationError("CONTEXT_CREATION_FAILED") from exc
        return self.publish(context)

    def publish(self, context: ExecutionContext) -> ExecutionContext:
        """Validate and atomically publish one preconstructed context.

        All work happens before the destination replacement.  Any validation,
        serialization, digest, or filesystem error leaves an existing
        publication untouched and is surfaced without a fallback payload.
        """
        try:
            serialized = serialize_execution_context(context)
            verified = deserialize_execution_context(
                serialized,
                expected_engine_version=self.expected_engine_version,
                expected_replay_uuid=context.replay_uuid,
            )
        except Exception as exc:
            raise ExecutionContextPublicationError("PUBLICATION_VALIDATION_FAILED") from exc

        self._atomic_write(serialized)
        return verified

    def _timestamp(self) -> str:
        value = self._clock()
        if not isinstance(value, datetime):
            raise ValueError("INVALID_CLOCK")
        utc = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return utc.isoformat(timespec="microseconds").replace("+00:00", "Z")

    def _atomic_write(self, serialized: bytes) -> None:
        temporary_path: Path | None = None
        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self.output_path.with_name(
                f".{self.output_path.name}.{uuid4().hex}.tmp"
            )
            with temporary_path.open("xb") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            temporary_path.chmod(0o444)
            os.replace(temporary_path, self.output_path)
        except Exception as exc:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise ExecutionContextPublicationError("ATOMIC_PUBLICATION_FAILED") from exc


def publish_execution_context(
    context: ExecutionContext,
    output_path: Path | str,
    *,
    expected_engine_version: str,
) -> ExecutionContext:
    """Publish through a short-lived production publisher."""
    return ExecutionContextPublisher(
        output_path, expected_engine_version=expected_engine_version
    ).publish(context)
