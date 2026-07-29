"""PR278 immutable lineage, single-admission, and non-execution tests."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from learning.release import ProductionReleaseAuthority, ReleaseRegistry
from learning.runtime_activation import ActivationRegistry, RuntimeActivationAuthority
from learning.runtime_admission import (RuntimeAdmissionAuthority, RuntimeAdmissionError,
    RuntimeAdmissionRegistry, RuntimeAdmissionRequest, RuntimeAdmissionResult)
from tests.learning.test_pr275_deployment_governance import promoted as promoted_fixture
from tests.learning.test_pr276_production_release_authority import bundle as release_bundle, context
from tests.learning.test_pr277_runtime_activation_authority import activation_bundle


@pytest.fixture
def activated(context):
    decision = ProductionReleaseAuthority().assess(release_bundle(context))
    releases = ReleaseRegistry().append(decision)
    chain = decision, releases, releases.entries[0], context["target_runtime_instance"]
    authority = RuntimeActivationAuthority()
    result = authority.activate(activation_bundle(chain))
    return result, authority.registry


def request(activated, admission_registry=None, **changes):
    result, activation_registry = activated
    registry = admission_registry or RuntimeAdmissionRegistry()
    values = dict(executor_handoff=result.executor_handoff,
        activation_registry=activation_registry,
        activation_registry_entry=result.registry_entry,
        admission_registry=registry,
        expected_admission_registry_identity=registry.registry_identity,
        admitted_at="2026-07-29T09:32:00Z")
    values.update(changes)
    return RuntimeAdmissionRequest(**values)


def test_admits_exactly_one_runtime_and_transfers_only_to_existing_v27(activated):
    authority = RuntimeAdmissionAuthority()
    result = authority.admit(request(activated))
    assert result.admission.runtime_admitted
    assert result.authority_transfer.executor_identity == "V27_PRODUCTION_EXECUTOR"
    assert result.authority_transfer.executor_version == "27.1"
    assert result.authority_transfer.execution_domain_authority_transferred
    assert not result.authority_transfer.broker_connection_performed
    assert not result.authority_transfer.trade_execution_performed
    assert not result.admission.broker_access_authorized
    assert not result.admission.trade_execution_authorized


def test_concurrent_replay_commits_exactly_one_admission(activated):
    authority = RuntimeAdmissionAuthority(); value = request(activated)
    def run():
        try: return authority.admit(value)
        except RuntimeAdmissionError as exc: return exc
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: run(), range(2)))
    assert sum(isinstance(x, RuntimeAdmissionResult) for x in outcomes) == 1
    assert len(authority.registry.entries) == 1


def test_forged_handoff_or_non_member_fails_and_records_evidence(activated):
    result, _ = activated
    forged = replace(result.executor_handoff, executor_version="wrong", handoff_identity="")
    authority = RuntimeAdmissionAuthority()
    with pytest.raises(RuntimeAdmissionError) as error:
        authority.admit(request(activated, executor_handoff=forged))
    assert error.value.evidence and not error.value.evidence.accepted
    assert len(authority.registry.rejections) == 1 and not authority.registry.entries

    authority = RuntimeAdmissionAuthority()
    with pytest.raises(RuntimeAdmissionError, match="MEMBERSHIP"):
        authority.admit(request(activated, activation_registry=ActivationRegistry()))
    assert len(authority.registry.rejections) == 1


def test_stale_registry_conflict_is_non_mutating(activated):
    authority = RuntimeAdmissionAuthority(); stale = request(activated)
    authority.admit(stale); current = authority.registry
    with pytest.raises(RuntimeAdmissionError, match="REGISTRY_CONFLICT"):
        authority.admit(stale)
    assert authority.registry.registry_identity == current.registry_identity


def test_admission_cannot_mutate_runtime_train_evaluate_or_generate_strategy(activated):
    admission = RuntimeAdmissionAuthority().admit(request(activated)).admission
    assert not admission.runtime_modification_authorized
    assert not admission.strategy_generation_authorized
    assert not admission.ai_training_authorized
    assert not admission.ai_evaluation_authorized
