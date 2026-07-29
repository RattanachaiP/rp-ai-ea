"""Fail-closed Runtime Activation Authority; no runtime or trading behavior."""
from learning.deployment.contracts import _utc

from .contracts import (ACTIVATION_CHECKS, ActivationEvidence,
                        ActivationRegistryEntry, ActivationResult,
                        ActivationValidation, ConsumedAuthorization,
                        RuntimeActivationEvent, validate_inputs)
from .registry import ActivationRegistry


class RuntimeActivationError(ValueError):
    """An authorization failed validation and was not consumed."""


class RuntimeActivationAuthority:
    def __init__(self, registry=None):
        self.registry = ActivationRegistry() if registry is None else registry
        # Reconstructing the registry validates its complete lineage.
        ActivationRegistry(self.registry.entries, self.registry.revocations,
                           self.registry.registry_identity)

    def activate(self, authorization, certificate, runtime_instance_identity,
                 executor_identity, activated_at):
        """Validate and atomically record one executor handoff.

        The returned event is evidence of a handoff, not an instruction to trade or
        a callback into runtime code.
        """
        try:
            validate_inputs(authorization, certificate)
            now = _utc(activated_at)
        except (AttributeError, TypeError, ValueError) as exc:
            raise RuntimeActivationError("ACTIVATION_INPUT_INVALID") from exc

        checks = {
            "authorization_signature": authorization.authorization_identity ==
                type(authorization)(**{name: getattr(authorization, name)
                    for name in authorization.__dataclass_fields__
                    if name != "authorization_identity"}).authorization_identity,
            "certificate_identity": authorization.certificate_identity == certificate.certificate_identity,
            "runtime_instance_identity": authorization.runtime_instance_identity == runtime_instance_identity == certificate.runtime_instance_identity,
            "executor_identity": authorization.executor_identity == executor_identity == certificate.executor_identity,
            "activation_generation": authorization.activation_generation == certificate.activation_generation,
            "validity_window": _utc(authorization.valid_from) <= now < _utc(authorization.valid_until),
            "single_use_status": not self.registry.is_consumed(authorization.authorization_identity),
            "revocation_status": not self.registry.is_revoked(authorization.authorization_identity, activated_at),
        }
        failed = next((name for name in ACTIVATION_CHECKS if not checks[name]), None)
        if failed:
            raise RuntimeActivationError("ACTIVATION_VALIDATION_FAILED:" + failed.upper())

        validations = tuple(ActivationValidation(name, True, "VALIDATED")
                            for name in ACTIVATION_CHECKS)
        evidence = ActivationEvidence(authorization.authorization_identity,
            certificate.certificate_identity, runtime_instance_identity,
            executor_identity, authorization.activation_generation, activated_at,
            validations)
        consumed = ConsumedAuthorization(authorization, activated_at,
                                         evidence.evidence_identity)
        event = RuntimeActivationEvent(consumed.consumption_identity,
            runtime_instance_identity, executor_identity, activated_at)
        entry = ActivationRegistryEntry(consumed, evidence, event,
            len(self.registry.entries) + 1,
            None if not self.registry.entries else self.registry.entries[-1].entry_identity)
        self.registry = self.registry.append(entry)
        return ActivationResult(evidence, consumed, entry, event, event)

    consume = activate
