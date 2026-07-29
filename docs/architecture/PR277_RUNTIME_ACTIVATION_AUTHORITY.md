# PR277 Runtime Activation Authority

## Authority boundary

The Runtime Activation Authority is the single, final consumer of a Production Release
`RuntimeActivationAuthorization`. Its immutable governance bundle binds the authoritative
PR276 decision, certificate, release manifest, authorization, Release Registry and exact
registry entry, the complete target runtime identity, the current Activation Registry,
the caller's expected registry identity, and the activation timestamp.

The authority validates the authorization's content-addressed identity integrity,
certificate and manifest binding, authoritative PR276 registry effectiveness, runtime
instance, executor identity and version, activation generation, runtime contract,
environment, artifact, validity window, single-use status, revocation status, and Activation
Registry snapshot. Certificate revocation, activation revocation, emergency rollback, and
supersession make a release ineffective. Every check must pass.

## Outputs and lifecycle

One successful consumption produces exactly one Activation Evidence record, one Consumed
Authorization, one append-only Activation Registry Entry, and one Runtime Activation Event.
The same event is the sole executor handoff. Registry predecessor identities make the audit
record tamper-evident, while the authorization identity uniqueness constraint prevents a
second activation from replaying the authorization.

Five immutable, hash-linked transition records establish the complete lifecycle:

`AUTHORIZED → VALIDATED → CONSUMED → RECORDED → HANDOFF → EXECUTOR`

Registry mutations use an expected-identity compare-and-swap under the authority's lock.
Every snapshot records `previous_registry_identity`. A stale or concurrent writer fails
without mutation. Rejected attempts append deterministic evidence without consuming the
authorization, and locally submitted revocations must name an authorization already known
to the authoritative PR276 Release Registry.

The explicit `ExecutorHandoff` binds the authorization, certificate, release manifest,
artifact, runtime contract, environment, executor identity and version, runtime instance,
activation generation, and authoritative Release Registry entry. Events bind this handoff
by immutable identity rather than Python object identity. It is a data-only handoff and
grants neither broker access nor trade execution. The authority
does not invoke executor or runtime callbacks. This authority cannot create an
authorization, alter runtime behavior, execute trades, connect to a broker, train or
evaluate models, or generate strategy.
