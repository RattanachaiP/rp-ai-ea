"""Execution-only authority for already-approved promotion decisions."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json, os, time
from pathlib import Path
from typing import Any, Mapping
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5
from learning.lifecycle import transition as lifecycle_transition
from .models import PromotionAuthorityConfig, PromotionRecord, PromotionTransaction
from .storage import PromotionRecordStorage

def _canonical(value): return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
def _digest(value): return sha256(_canonical(value).encode()).hexdigest()
def _now(): return datetime.now(timezone.utc)
def _iso(value): return value.isoformat(timespec="microseconds").replace("+00:00", "Z")

class PromotionAuthority:
    """Consumes one signed decision report and requests, never performs, a lifecycle transition."""
    def __init__(self, *, config=None, root="learning_data", lifecycle_service=None, clock=_now):
        self.config=config or PromotionAuthorityConfig(); self.storage=PromotionRecordStorage(root)
        self.root=Path(root); self.lifecycle_service=lifecycle_service or lifecycle_transition; self.clock=clock
    @staticmethod
    def _data(report):
        return report.to_dict() if hasattr(report, "to_dict") else report if isinstance(report, Mapping) else None
    @staticmethod
    def _semantic(data): return data["knowledge_uuid"]
    @contextmanager
    def _lock(self, semantic):
        locks=self.root/"promotion_locks"; locks.mkdir(parents=True,exist_ok=True)
        path=locks/(sha256(semantic.encode()).hexdigest()+".lock"); fd=None
        try:
            fd=os.open(path, os.O_CREAT|os.O_EXCL|os.O_WRONLY); os.write(fd,str(os.getpid()).encode()); yield
        except FileExistsError as exc: raise RuntimeError("PROMOTION_LOCK_CONTENDED") from exc
        finally:
            if fd is not None: os.close(fd); path.unlink(missing_ok=True)
    def validate(self, report):
        data=self._data(report)
        if not isinstance(data, Mapping): raise ValueError("MISSING_PROMOTION_DECISION_REPORT")
        required={"decision_uuid","knowledge_uuid","decision","decision_status","snapshot_digest","qualification_digest","policy_version","created_at","schema_version","configuration_digest","signature"}
        if not required.issubset(data) or any(not isinstance(data[k],str) or not data[k] for k in required): raise ValueError("INVALID_PROMOTION_DECISION_REPORT")
        try: UUID(data["decision_uuid"]); UUID(data["knowledge_uuid"])
        except (ValueError, TypeError, AttributeError): raise ValueError("INVALID_PROMOTION_UUID")
        if data["decision"] != "PROMOTE" or data["decision_status"] != "APPROVED": raise ValueError("PROMOTION_DECISION_NOT_EXECUTABLE")
        if data["schema_version"] != self.config.expected_schema_version: raise ValueError("UNKNOWN_PROMOTION_DECISION_SCHEMA")
        if data["policy_version"] not in self.config.allowed_policy_versions: raise ValueError("UNAPPROVED_PROMOTION_CONFIGURATION")
        for name in ("snapshot_digest","qualification_digest","configuration_digest"):
            if len(data[name]) != 64 or any(c not in "0123456789abcdef" for c in data[name].lower()): raise ValueError("INVALID_PROMOTION_DIGEST")
        unsigned=dict(data); signature=unsigned.pop("signature")
        if signature != _digest(unsigned): raise ValueError("INVALID_PROMOTION_SIGNATURE")
        try: created=datetime.fromisoformat(data["created_at"].replace("Z","+00:00"))
        except ValueError: raise ValueError("INVALID_PROMOTION_TIMESTAMP")
        if created.tzinfo is None: raise ValueError("INVALID_PROMOTION_TIMESTAMP")
        age=(self.clock()-created).total_seconds()
        if age < 0 or age > self.config.maximum_decision_age_seconds: raise ValueError("EXPIRED_PROMOTION_DECISION")
        return dict(data)
    def _existing(self, decision_uuid): return next((r for r in self.storage.all() if r.decision_uuid==decision_uuid),None)
    def execute(self, report):
        data=self.validate(report); existing=self._existing(data["decision_uuid"])
        if existing: return existing
        tx=PromotionTransaction(str(uuid4()),data["decision_uuid"],data["knowledge_uuid"],self._semantic(data)); tx.set_state("VALIDATING")
        try:
            with self._lock(tx.semantic_identity):
                tx.set_state("LOCKED"); existing=self._existing(tx.decision_uuid)
                if existing: return existing
                tx.set_state("EXECUTING"); timestamp=_iso(self.clock())
                transition={"knowledge_uuid":tx.knowledge_uuid,"previous_state":"VERIFIED","new_state":"ACTIVE","triggering_component":"PromotionAuthority","reason":f"approved promotion decision {tx.decision_uuid}","governance_version":self.config.governance_version,"lifecycle_version":self.config.lifecycle_version,"timestamp":timestamp,"transition_uuid":str(uuid5(NAMESPACE_URL,tx.decision_uuid))}
                # The audit payload is constructed and durably staged before the lifecycle
                # request.  A failed request discards that uncommitted staging record.
                record=PromotionRecord(str(uuid5(NAMESPACE_URL,tx.decision_uuid+":record")),tx.decision_uuid,tx.knowledge_uuid,transition,timestamp,self.config.operator,self.config.version,tx.transaction_uuid)
                tx.set_state("COMMITTING"); self.storage.write(record); tx.record=record
                event=self.lifecycle_service(**transition)
                event_data=event.to_dict() if hasattr(event,"to_dict") else transition
                if any(event_data.get(key) != value for key, value in transition.items()):
                    # Services may add audit metadata such as a schema version, but never
                    # alter the transition requested by this authority.
                    raise RuntimeError("LIFECYCLE_TRANSITION_MISMATCH")
                tx.set_state("COMPLETED"); return record
        except Exception as exc:
            tx.error=str(exc); self.rollback(tx); raise
    def rollback(self, transaction):
        transaction.set_state("ROLLED_BACK")
        if transaction.record is not None:
            self.storage.discard_uncommitted(transaction.record)
        rollback=getattr(self.lifecycle_service,"rollback",None)
        if callable(rollback): rollback(transaction)
        return transaction
    def history(self, decision_uuid=None):
        records=self.storage.all(); return tuple(r for r in records if decision_uuid is None or r.decision_uuid==decision_uuid)
