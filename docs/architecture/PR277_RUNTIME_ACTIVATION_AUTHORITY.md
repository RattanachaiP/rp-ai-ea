# PR277 Runtime Activation Authority

## Authority boundary

The Runtime Activation Authority is the single, final consumer of a Production Release
`RuntimeActivationAuthorization`. It accepts only that authorization, its Production
Release Certificate, the runtime instance identity, and the executor identity. The
caller-supplied activation instant is used only to evaluate the authorization's immutable
validity window and timestamp the evidence.

The authority validates the authorization's content-addressed signature, certificate
identity, runtime instance, executor, activation generation, validity window, single-use
status, and revocation status. Every check must pass. Expired, mismatched, forged, replayed,
or revoked authorizations fail closed and produce no registry entry or handoff.

## Outputs and lifecycle

One successful consumption produces exactly one Activation Evidence record, one Consumed
Authorization, one append-only Activation Registry Entry, and one Runtime Activation Event.
The same event is the sole executor handoff. Registry predecessor identities make the audit
record tamper-evident, while the authorization identity uniqueness constraint prevents a
second activation from replaying the authorization.

The evidence records the complete lifecycle:

`AUTHORIZED → VALIDATED → CONSUMED → RECORDED → HANDOFF → EXECUTOR`

The event is a data-only handoff. It grants neither broker access nor trade execution and
does not invoke executor or runtime callbacks. This authority cannot create an
authorization, alter runtime behavior, execute trades, connect to a broker, train or
evaluate models, or generate strategy.
