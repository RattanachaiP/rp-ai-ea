"""PR180 secure bridge from PR179 registry evidence to advisory packages only."""

from dataclasses import replace

from learning.knowledge_registry import (KnowledgeRegistryError, KnowledgeRegistryReport,
                                         KnowledgeRegistryRepository, RegistryRecord)
from learning.knowledge_registry.identity import digest as registry_digest

from .exceptions import RuntimeKnowledgeError
from .models import (RuntimeKnowledgeConsumptionReport, RuntimeKnowledgePackage,
                     RuntimeKnowledgeSnapshot)
from .repository import RuntimeKnowledgeRepository


class RuntimeKnowledgeGate:
    """Verify canonical PR179 artifacts and package them without selecting or activating them."""

    runtime_engine_version = "PR180.1.0"
    runtime_policy_version = "PR180-CONSUMPTION-POLICY.1.0"

    def __init__(self, registry_repository=None, repository=None, *,
                 runtime_engine_version=None, runtime_policy_version=None):
        self.registry_repository = registry_repository or KnowledgeRegistryRepository()
        self.repository = repository or RuntimeKnowledgeRepository()
        self.runtime_engine_version = runtime_engine_version or type(self).runtime_engine_version
        self.runtime_policy_version = runtime_policy_version or type(self).runtime_policy_version
        if not isinstance(self.registry_repository, KnowledgeRegistryRepository):
            raise RuntimeKnowledgeError("INVALID_REGISTRY")
        if not isinstance(self.repository, RuntimeKnowledgeRepository):
            raise RuntimeKnowledgeError("INVALID_RUNTIME_REPOSITORY")
        if not isinstance(self.runtime_engine_version, str) or not self.runtime_engine_version:
            raise RuntimeKnowledgeError("ENGINE_VERSION_MISMATCH")
        if not isinstance(self.runtime_policy_version, str) or not self.runtime_policy_version:
            raise RuntimeKnowledgeError("POLICY_VERSION_MISMATCH")

    def consume(self, source):
        if type(source) not in (KnowledgeRegistryReport, RegistryRecord):
            raise RuntimeKnowledgeError("INVALID_REGISTRY")
        records, source_fields, snapshot, generated_at = self._verify_source(source)
        self._verify_partition(records)
        existing = self.repository.packages()
        if existing and any((item.runtime_engine_version != self.runtime_engine_version
                             for item in existing)):
            raise RuntimeKnowledgeError("ENGINE_VERSION_MISMATCH")
        if existing and any((item.runtime_policy_version != self.runtime_policy_version
                             for item in existing)):
            raise RuntimeKnowledgeError("POLICY_VERSION_MISMATCH")
        by_registry = {item.registry_uuid: item for item in existing}
        packages = []
        new_count = duplicate_count = 0
        for record in records:
            package = self._package(record, generated_at)
            prior = by_registry.get(record.registry_uuid)
            if prior is not None:
                if prior != package:
                    raise RuntimeKnowledgeError("REPLAY_MISMATCH")
                package = prior
                duplicate_count += 1
            else:
                self.repository.save(package)
                by_registry[record.registry_uuid] = package
                new_count += 1
            packages.append(package)
        identities = self.repository.identities()
        repository_digest = self.repository.digest()
        previous = self.repository.latest_snapshot()
        if (previous is not None and previous.package_identities == identities
                and previous.source_registry_snapshot_uuid == snapshot.snapshot_uuid
                and previous.source_registry_snapshot_digest == snapshot.snapshot_digest):
            runtime_snapshot = previous
        else:
            runtime_snapshot = RuntimeKnowledgeSnapshot.create(
                source_registry_snapshot_uuid=snapshot.snapshot_uuid,
                source_registry_snapshot_digest=snapshot.snapshot_digest,
                source_registry_repository_digest=snapshot.repository_digest,
                package_identities=identities, package_count=len(identities),
                repository_digest=repository_digest,
                runtime_policy_version=self.runtime_policy_version,
                runtime_engine_version=self.runtime_engine_version,
                previous_snapshot_uuid=previous.snapshot_uuid if previous else None,
                previous_snapshot_digest=previous.snapshot_digest if previous else None,
                generated_at=generated_at, advisory_only=True)
            self.repository.save_snapshot(runtime_snapshot)
        return RuntimeKnowledgeConsumptionReport.create(
            **source_fields, source_registry_snapshot_uuid=snapshot.snapshot_uuid,
            source_registry_snapshot_digest=snapshot.snapshot_digest,
            source_registry_repository_digest=snapshot.repository_digest,
            runtime_packages=tuple(packages), processed_record_count=len(packages),
            new_package_count=new_count, duplicate_package_count=duplicate_count,
            repository_digest=repository_digest, snapshot_uuid=runtime_snapshot.snapshot_uuid,
            snapshot_digest=runtime_snapshot.snapshot_digest,
            runtime_policy_version=self.runtime_policy_version,
            runtime_engine_version=self.runtime_engine_version,
            generated_at=generated_at, advisory_only=True)

    run = consume

    def _verify_source(self, source):
        try:
            latest = self.registry_repository.latest_snapshot()
            stored_records = self.registry_repository.records()
        except KnowledgeRegistryError as exc:
            message = str(exc)
            if "PARTITION" in message:
                raise RuntimeKnowledgeError("MIXED_REGISTRY_PARTITION") from exc
            raise RuntimeKnowledgeError("BROKEN_REGISTRY_PROVENANCE") from exc
        if latest is None:
            raise RuntimeKnowledgeError("INVALID_REGISTRY")
        by_uuid = {item.registry_uuid: item for item in stored_records}
        snapshots = {item.snapshot_uuid: item for item in self.registry_repository.snapshots()}
        if type(source) is KnowledgeRegistryReport:
            snapshot = snapshots.get(source.snapshot_uuid)
            if snapshot is None or snapshot.snapshot_digest != source.snapshot_digest:
                raise RuntimeKnowledgeError("SNAPSHOT_MISMATCH")
            if snapshot.repository_digest != source.repository_digest:
                raise RuntimeKnowledgeError("REGISTRY_DIGEST_MISMATCH")
        else:
            stored = by_uuid.get(source.registry_uuid)
            if stored is None:
                raise RuntimeKnowledgeError("INVALID_REGISTRY")
            if stored.registry_digest != source.registry_digest:
                raise RuntimeKnowledgeError("REGISTRY_DIGEST_MISMATCH")
        try:
            clean = replace(source)
        except (TypeError, ValueError) as exc:
            raise RuntimeKnowledgeError("BROKEN_REGISTRY_PROVENANCE") from exc
        if type(clean) is KnowledgeRegistryReport:
            records = clean.registry_records
            fields = {"source_artifact_type": "KNOWLEDGE_REGISTRY_REPORT",
                      "source_registry_report_uuid": clean.report_uuid,
                      "source_registry_uuid": None}
            generated_at = clean.generated_at
        else:
            snapshot = latest
            records = (clean,)
            fields = {"source_artifact_type": "KNOWLEDGE_REGISTRY_RECORD",
                      "source_registry_report_uuid": None,
                      "source_registry_uuid": clean.registry_uuid}
            generated_at = clean.recorded_at
        for record in records:
            stored = by_uuid.get(record.registry_uuid)
            if stored is None:
                raise RuntimeKnowledgeError("INVALID_REGISTRY")
            if stored.registry_digest != record.registry_digest or stored != record:
                raise RuntimeKnowledgeError("REGISTRY_DIGEST_MISMATCH")
            if record.registry_state != "ADVISORY_ENTRY_RECORDED" or record.advisory_only is not True:
                raise RuntimeKnowledgeError("INVALID_REGISTRY")
        return tuple(records), fields, snapshot, generated_at

    @staticmethod
    def _verify_partition(records):
        if not records:
            raise RuntimeKnowledgeError("INVALID_REGISTRY")
        registry_partition = {(item.registry_engine_version,
                               item.registry_admission_policy_uuid,
                               item.registry_admission_policy_digest,
                               item.registry_admission_policy_version) for item in records}
        if len(registry_partition) != 1:
            raise RuntimeKnowledgeError("MIXED_REGISTRY_PARTITION")
        promotion_partition = {(item.source_promotion_engine_version,
                                item.source_promotion_policy_uuid,
                                item.source_promotion_policy_digest,
                                item.source_promotion_policy_version) for item in records}
        validation_partition = {(item.source_validator_version,
                                 item.source_validation_policy_version,
                                 item.source_validation_config_digest) for item in records}
        if len(promotion_partition) != 1 or len(validation_partition) != 1:
            raise RuntimeKnowledgeError("POLICY_VERSION_MISMATCH")
        provenance = {}
        for item in records:
            replay = (item.source_digest, item.replay_digest, item.source_memory_uuid,
                      item.source_pattern_uuid, item.source_pattern_hash)
            prior = provenance.setdefault(item.knowledge_uuid, replay)
            if prior != replay:
                raise RuntimeKnowledgeError("REPLAY_MISMATCH")

    def _package(self, record, generated_at):
        return RuntimeKnowledgePackage.create(
            registry_uuid=record.registry_uuid, registry_digest=record.registry_digest,
            knowledge_uuid=record.knowledge_uuid, knowledge_version=record.knowledge_version,
            pattern_uuid=record.source_pattern_uuid, pattern_hash=record.source_pattern_hash,
            promotion_uuid=record.source_promotion_uuid,
            validation_uuid=record.source_validation_uuid, memory_uuid=record.source_memory_uuid,
            policy_uuid=record.source_policy_uuid, source_digest=record.source_digest,
            replay_digest=record.replay_digest,
            runtime_policy_version=self.runtime_policy_version,
            runtime_engine_version=self.runtime_engine_version,
            generated_at=generated_at, advisory_only=True)
