# PR278 Runtime Admission Authority

## Sole input and authority boundary

PR278 consumes the immutable `ExecutorHandoff` emitted by PR277. The accompanying PR277
Activation Registry and exact entry are read-only origin proofs, never alternate authority
inputs. The admission authority reconstructs every proof at its trust boundary and validates
the handoff identity, authoritative registry membership and integrity, accepted activation
evidence, authorization, certificate, manifest, runtime, V27 Executor, lifecycle and event
lineage before admitting anything. It fails closed on every mismatch.

The only admitted target is the exact runtime instance named by the handoff, using the
existing `V27_PRODUCTION_EXECUTOR` version `27.1`. One handoff and one runtime instance can
produce exactly one admission. Admission uses an expected-registry-identity compare-and-swap
under a lock, so stale callers and concurrent replays cannot create a second admission.

## Immutable evidence and transfer

A successful decision atomically records one content-addressed Runtime Admission Evidence,
one Runtime Admission, one append-only Admission Registry Entry, and one data-only Executor
Authority Transfer. Registry and entry predecessor identities preserve immutable lineage.
Rejected validations record immutable negative evidence without admitting the runtime.

The transfer names the existing V27 Production Executor as the recipient of execution-domain
authority; PR278 does not invoke it. The admission authority never executes a trade, connects
to a broker, modifies Runtime, generates strategy, trains AI, or evaluates AI. Its admission
record explicitly denies all six capabilities. No callback, broker object, order instruction,
strategy input, model input, or mutable runtime object exists at the PR278 boundary.
