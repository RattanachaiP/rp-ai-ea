# RAIP Version Compatibility

Consumers must use semantic-version compatibility: the major version must be supported,
and optional unknown fields must be ignored. Producers may add optional fields in a minor or
patch version but must not remove or change the meaning of required fields. A major version
change requires a migration plan, dual-read period where practical, and a registry update.

V9 accepts Executive Package `7.x` as its input contract and emits only V9 `9.0.0` validation
documents. An unsupported or missing contract version must result in safe non-processing, never
fallback interpretation.

V10 accepts only the exact source versions declared by its immutable
`learning_intake_policy.json`: Governance `6.0.0`, Executive Package `7.0.0`, and Validation
`9.0.0`. It emits only V10 `10.0.0` qualification documents. A missing, unsupported, or
policy-incompatible source version must result in deferred or rejected offline qualification;
it must never be interpreted as a compatible document.
