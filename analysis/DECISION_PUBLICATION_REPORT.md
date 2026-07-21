# Decision Publication Layer — V27.5 Report

## Ownership

`runtime/decision_publication.py` is the only V27.5 component that serializes
and publishes a `RuntimeDecisionPayload` to `decision.json`.  It consumes the
validated DTO from the Writer Adapter; it does not import the Decision
Pipeline, calculate trading values, alter a decision, access MT5, invoke a
broker, or execute orders.

## Publication contract

Each successful publication emits exactly one UTF-8 JSON document named
`decision.json`.  It preserves the adapter payload fields and adds publication
metadata: `schema_version: "2.0"`, `brain_version: "27.4"`,
`runtime_version: "27.5"`, monotonically increasing `sequence_id`,
`heartbeat_unix`, and UTC ISO-8601 `published_at`.

## Serialization and validation policy

The publisher accepts only the frozen `RuntimeDecisionPayload` contract with
the expected Writer Adapter schema.  All mandatory primitive fields, finite
numeric values, tuple string traces/reasons, booleans, and executable/fail-safe
consistency are validated before serialization.  JSON is encoded
deterministically with sorted keys and `allow_nan=False`; enums, custom
classes, non-finite values, and other unserializable inputs are rejected.

## Atomic write, heartbeat, and sequence

The full JSON byte sequence is written only to sibling `decision.tmp`, flushed,
fsynced, closed, then atomically replaced into `decision.json` with
`os.replace`.  The sequence counter is recovered from a valid existing output
on publisher construction and advances only after a successful replacement.
Every successful publication derives both freshness fields from one UTC clock
sample.

## Fail-safe publication

An invalid runtime payload is never written.  Instead the publication layer
atomically writes valid JSON with `decision=WAIT`, `direction=NONE`,
`fail_safe=true`, and `executable=false`, retaining an auditable publication
failure reason.  A filesystem failure is raised rather than falsely reported
as a successful publication.

## Compatibility and limitations

The published document retains every current Writer Adapter runtime field and
adds only the required publication metadata.  It does not yet integrate the
legacy V26 writer, which remains a separate transitional writer with its own
legacy aliases.  This component intentionally makes no legacy field removals.

## Next phase — Writer Integration

Writer Integration must route the validated `RuntimeDecisionPayload` to this
publisher and retire every competing runtime `decision.json` writer.  That
phase must preserve required legacy consumer fields and verify the Executor
contract without moving decision, Writer Adapter, or Executor logic here.
