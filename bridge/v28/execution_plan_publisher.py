"""Atomic publication of an immutable ExecutionPlan without reinterpretation."""
from __future__ import annotations
from hashlib import sha256
import json, os
from pathlib import Path
from tempfile import NamedTemporaryFile
from .execution_plan import ExecutionPlan, identity
from .publisher_contract import PublishedExecutionPlan, canonical_json


def publication_for(plan: ExecutionPlan, *, publisher_authority: str, publisher_instance_identity: str,
                    publication_timestamp: str, destination_identity: str, generation: int,
                    policy_reference: str) -> PublishedExecutionPlan:
    if plan.replay_identity != identity("V28_EXECUTION_PLAN_REPLAY", plan.canonical_payload()): raise ValueError("EXECUTION_PLAN_INVALID")
    encoded = canonical_json(plan.canonical_payload())
    values = dict(canonical_plan_json=encoded, publisher_authority=publisher_authority,
        publisher_instance_identity=publisher_instance_identity, publication_timestamp=publication_timestamp,
        destination_identity=destination_identity, generation=generation, policy_reference=policy_reference,
        schema_version="V28.PUBLISHED_EXECUTION_PLAN.2.0", execution_plan_replay_identity=plan.replay_identity,
        decision_replay_identity=plan.decision_replay_identity, runtime_sequence_id=plan.runtime_sequence_id,
        canonical_payload_hash=sha256(encoded.encode()).hexdigest())
    return PublishedExecutionPlan(**values, publication_replay_identity=identity("V28_EXECUTION_PUBLICATION_REPLAY", values))


class ExecutionPlanPublisher:
    def __init__(self, path: Path | str, *, publisher_authority: str, publisher_instance_identity: str,
                 destination_identity: str, policy_reference: str) -> None:
        self.path=Path(path); self.authority=publisher_authority; self.instance=publisher_instance_identity
        self.destination=destination_identity; self.policy=policy_reference
    def publish(self, plan: ExecutionPlan, *, publication_timestamp: str, generation: int) -> PublishedExecutionPlan:
        publication=publication_for(plan,publisher_authority=self.authority,publisher_instance_identity=self.instance,
            publication_timestamp=publication_timestamp,destination_identity=self.destination,generation=generation,policy_reference=self.policy)
        encoded=canonical_json(publication.canonical_payload() | {"publication_replay_identity":publication.publication_replay_identity}).encode()
        self.path.parent.mkdir(parents=True,exist_ok=True); temporary=None
        try:
            with NamedTemporaryFile("wb",dir=self.path.parent,prefix=f".{self.path.name}.",delete=False) as stream:
                temporary=Path(stream.name); stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary,self.path); directory=os.open(self.path.parent,os.O_RDONLY)
            try: os.fsync(directory)
            finally: os.close(directory)
        except Exception:
            if temporary is not None: temporary.unlink(missing_ok=True)
            raise
        return publication
