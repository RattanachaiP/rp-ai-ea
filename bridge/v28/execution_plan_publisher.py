"""Atomic publication of an immutable ExecutionPlan without reinterpretation."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .execution_plan import ExecutionPlan, identity
from .publisher_contract import PublishedExecutionPlan


def publication_for(plan: ExecutionPlan) -> PublishedExecutionPlan:
    if plan.replay_identity != identity("V28_EXECUTION_PLAN_REPLAY", plan.canonical_payload()):
        raise ValueError("EXECUTION_PLAN_INVALID")
    values = {"payload": plan.canonical_payload(), "execution_plan_replay_identity": plan.replay_identity,
              "decision_replay_identity": plan.decision_replay_identity, "runtime_sequence_id": plan.runtime_sequence_id,
              "schema_version": "V28.PUBLISHED_EXECUTION_PLAN.1.0"}
    return PublishedExecutionPlan(**values, execution_replay_identity=identity("V28_EXECUTION_PUBLICATION_REPLAY", values))


class ExecutionPlanPublisher:
    def __init__(self, path: Path | str) -> None: self.path = Path(path)

    def publish(self, plan: ExecutionPlan) -> PublishedExecutionPlan:
        publication = publication_for(plan)
        document = publication.canonical_payload() | {"execution_replay_identity": publication.execution_replay_identity}
        encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile("wb", dir=self.path.parent, prefix=f".{self.path.name}.", delete=False) as stream:
                temporary = Path(stream.name); stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY)
            try: os.fsync(directory)
            finally: os.close(directory)
        except Exception:
            if temporary is not None: temporary.unlink(missing_ok=True)
            raise
        return publication

