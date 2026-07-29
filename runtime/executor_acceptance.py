"""Executor-origin PR279 acceptance attestation producer.

This module records acceptance only. It has no runtime start, broker, order, or trade path.
"""
import hashlib
import hmac
import json

from learning.executor_acknowledgement.contracts import ExecutorAcceptanceAttestation


def _signature(payload, signing_key):
    canonical=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
    return hmac.new(signing_key,canonical,hashlib.sha256).hexdigest()


def produce_executor_acceptance_attestation(*, executor_admission_authorization,
        admission_registry_entry, executor_instance_identity, executor_session_identity,
        acknowledgement_authority_identity, accepted_at, nonce, signing_key):
    """Create the signed acceptance artifact inside the existing V27 executor boundary."""
    admission=admission_registry_entry.admission_authorization
    evidence=admission_registry_entry.evidence
    values={"admission_authorization_identity":admission.authorization_identity,
        "executor_admission_authorization_identity":executor_admission_authorization.authorization_identity,
        "executor_identity":executor_admission_authorization.executor_identity,
        "executor_version":executor_admission_authorization.executor_version,
        "executor_instance_identity":executor_instance_identity,
        "executor_session_identity":executor_session_identity,
        "runtime_instance_identity":executor_admission_authorization.runtime_instance_identity,
        "activation_generation":executor_admission_authorization.activation_generation,
        "artifact_identity":evidence.artifact_identity,
        "runtime_contract_identity":evidence.runtime_contract_identity,
        "target_environment_identity":evidence.target_environment_identity,
        "executor_policy_identity":admission.policy_identity,
        "acknowledgement_authority_identity":acknowledgement_authority_identity,
        "accepted_at":accepted_at,"nonce":nonce}
    return ExecutorAcceptanceAttestation(**values,signature=_signature(values,signing_key))
