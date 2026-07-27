# PR225 — Demo Operational Execution Validation

## Verdict

**NOT EXECUTED — DEMO OPERATION NOT VERIFIED.**

This repository checkout cannot truthfully produce the requested operational
certification.  The validation host has no MT5 terminal (or Wine executable),
no Demo-account configuration, and no broker session.  Consequently no live
publication, `OrderSend`, ticket, position, modification, close, terminal
restart, or broker-fill timestamp was observed.  An `OK` result must never be
inferred from a unit test, a simulated broker, or the deterministic PR224 run.

This report is the PR225 evidence record.  It deliberately makes no production
code change and preserves the governed architecture.  It also defines the
minimum evidence that an operator must attach after running on the designated
MT5 Demo host.  Until that evidence exists, every live-only acceptance item is
`BLOCKED`, not `OK`.

## Validation identity and repository integrity report

| Item | Observed value | Status |
|---|---|---|
| Requested baseline | `b1c1f5a` | OK |
| Full checkout HEAD before this report | `b1c1f5aa057fd9f35831ca754dc91030b9345d63` | OK |
| Requested branch | `codex-dev` | NOT PRESENT AS CHECKED OUT |
| Checked-out branch supplied by the environment | `work` | OBSERVED |
| Production source changes made by PR225 | none | OK |
| Writer/Reader/Bootstrap/Diagnostics changes | none | OK |
| Package engine/Executor/governance changes | none | OK |

The baseline was established with `git rev-parse HEAD`; the worktree and final
change set must be checked again before certification.  The report-only commit
is expected to change HEAD, but must not change runtime behavior.  Certification
requires recording `git status --short`, `git diff --stat b1c1f5a..HEAD`, and
`git diff --name-only b1c1f5a..HEAD` in the evidence bundle.

## Host preflight and blocking conditions

The following preflight was performed on 2026-07-27 UTC:

```text
Python: 3.14.4
terminal64.exe on PATH: absent
Wine on PATH: absent
MT5 terminal under /workspace: absent
MT5/Demo/Broker configuration variable names: absent
```

Credentials must not be committed or copied into this report.  An operator
must provide a running, authenticated **Demo** terminal, the canonical V14
Writer, the governed Python runtime, the production Executor integration, and
a market session in which the configured symbol is tradable.  Account type and
server name should be captured with the login redacted.

There is also an integration fact that must be resolved by evidence before a
live order is authorized: the PR189/PR190 bootstrap exports
`RP_EXECUTION_PACKAGE_UUID` and invokes the V26 runtime, while the current
`runtime.executor.Executor.execute` public input is a `WriterReadResult`.
PR224 stopped at “Executor Input” and explicitly excluded `OrderSend`.  PR225
must demonstrate, from the deployed production composition (without inventing
a new authority), exactly how the immutable PR190 package becomes the single
canonical Executor input.  If that deployed linkage does not exist, execution
must remain disabled and PR225 fails closed.

## Demo execution and UUID lineage report

For one and only one authorized trade, collect a single append-only event log.
Every event needs an RFC 3339 UTC wall-clock timestamp, monotonic timestamp,
process identity, event name, outcome, and relevant immutable identity/digest.
Secrets and account numbers must be redacted.  The minimum chain is:

| Stage | Required proof | Current result |
|---|---|---|
| Writer | heartbeat, sequence, source UUID, timestamp, final file SHA-256 and successful UTF-8/JSON decode | BLOCKED |
| Reader | every consecutive sequence, freshness decision, source UUID, read SHA-256 | BLOCKED |
| Context | Context UUID and parent/source identity | BLOCKED |
| Intelligence | Intelligence UUID and exact Context UUID | BLOCKED |
| Activation | Activation UUID/record and selected exact Intelligence UUID; activation count = 1 | BLOCKED |
| Recommendation | Recommendation UUID and exact Intelligence UUID | BLOCKED |
| Readiness | Readiness UUID and exact Recommendation UUID | BLOCKED |
| Environment | Environment UUID and exact Readiness UUID | BLOCKED |
| Feasibility | Feasibility UUID and exact Readiness/Environment UUIDs | BLOCKED |
| PR189 Package | Package UUID, digest, `created_at`, all three exact parent UUIDs, repository snapshot | BLOCKED |
| PR190 Consumer | requested/returned Package UUID and bytes before/after consumption | BLOCKED |
| Executor | one receipt, Package UUID, Recommendation UUID, digest, timestamp, unchanged payload SHA-256 | BLOCKED |
| `OrderSend` | complete redacted request, result/retcode and description | BLOCKED |
| Broker | accepted ticket/deal/position IDs, magic number, comment and fill | BLOCKED |

Any absent, duplicated, or unequal identity is a lineage break.  On a lineage
break the operator must preserve the evidence, prevent `OrderSend`, mark the
run `FAILED`, and must not continue by selecting a “latest” record.

### Package immutability comparison

Capture the package file bytes immediately after PR189 persistence, immediately
after PR190 load, and immediately before Executor submission.  Record byte
length and SHA-256 for all three.  Certification requires all lengths and
digests to match and the persisted PR189 package digest to validate.  A Python
object equality assertion alone is not byte-for-byte evidence.

## Writer and Reader live-publication protocol

Observe at least 100 consecutive real Writer publications without modifying
the Writer or Reader.  A filesystem observer may copy each completed visible
publication to a timestamped evidence directory; it must not write to or lock
`market_state.json`.  For every copy:

1. Read as raw bytes, strictly decode UTF-8, parse exactly one JSON document,
   and calculate SHA-256.
2. Record file identity/size/mtime before and after the read.  Discard and retry
   the observation if metadata changes during the evidence copy.
3. Record `heartbeat_unix`, `sequence_id`, publication timestamp and observer
   timestamp.
4. Require a strictly consecutive sequence (`current == previous + 1`), a
   fresh heartbeat under the governed Reader policy, and matching bytes at the
   Reader boundary.
5. Record the temporary-to-final rename events (or equivalent platform file
   events) as atomic-publication evidence.  Merely parsing the final file does
   not prove the absence of a non-atomic write.

The run fails on a gap, rollback, duplicate treated as new, partial/invalid
decode, stale acceptance, or a Reader value inconsistent with the captured
publication.  “Detects every publication” is only claimed for the bounded
observation interval and its recorded sequence range.

## Position lifecycle and restart recovery report

Record broker position snapshots and runtime state transitions for this exact
ticket.  Required observed order is:

```text
OPEN -> MODIFY -> BREAKEVEN -> TRAIL -> PARTIAL (only when enabled)
     -> CLOSE -> POSITION REMOVED -> RUNTIME READY
```

If partial close is disabled, record the governing configuration and mark it
`NOT APPLICABLE`, never silently `OK`.  Each transition requires ticket,
position identifier, volume, price, SL/TP, broker retcode, and timestamps.

While the position is open, perform three separate scenarios, returning the
system to a known state between scenarios:

1. Restart only the Python runtime.
2. Restart only the MT5 terminal and wait for authenticated synchronization.
3. Restart only the Executor process/service.

For each scenario preserve pre-restart repository/package hashes and the open
position snapshot.  After restart prove repository reload, the same activation
and package identities, broker position synchronization, and zero additional
`OrderSend` calls/tickets.  A process restart is not proof of recovery unless
all of these postconditions are recorded.

Current result for lifecycle, all restart scenarios, recovery, and return to
ready: **BLOCKED — no Demo position or MT5 terminal was available.**

## Failure injection report

Failure injection must run on an isolated copy of the Demo runtime state, one
case at a time, with live execution disabled until the rejection checkpoint.
Never corrupt the canonical production repository merely to create evidence.

| Injection | Required fail-closed observation | Current result |
|---|---|---|
| Missing `market_state.json` | no decision/package/order; explicit missing-input reason | BLOCKED |
| Stale heartbeat | Reader/runtime rejects; no downstream order | BLOCKED |
| Sequence rollback | publication rejected; prior state not re-executed | BLOCKED |
| Corrupted JSON/UTF-8 | parse rejected; no cached state substituted | BLOCKED |
| Duplicate package | exactly one consumption/submission; duplicate reason recorded | BLOCKED |
| Broker rejection | exact retcode/reason captured; no ticket/position invented | BLOCKED |

For each case attach the injected input hash, start/end time, rejection event,
zero-`OrderSend` proof (except the intentional broker-rejection request), and
the subsequent clean recovery-to-ready event.  Exceptions, hangs, silent cache
fallback, retries that can duplicate exposure, and ambiguous acceptance all
fail certification.

## Latency report

No latency numbers are reported because no live events were observed.  Do not
reuse PR224 deterministic timings as Demo latency.  On the Demo host use one
monotonic clock domain where possible; otherwise record the measured clock
offset/uncertainty and never report false sub-millisecond precision.

Capture both per-hop and elapsed-from-Writer values for:

```text
Writer -> Reader -> Context -> Intelligence -> Activation -> Recommendation
-> Readiness -> Environment -> Feasibility -> Package -> Consumer -> Executor
-> OrderSend -> Broker Fill
```

At minimum report count, minimum, median, p95, maximum, unit, clock source, and
sample inclusion rules.  For the single acceptance trade, include every raw
checkpoint.  Keep broker round-trip (`OrderSend` to response) distinct from
broker-fill latency when those events differ.

## Operational health report

```text
====================================
Writer................BLOCKED
Reader................BLOCKED
Context...............BLOCKED
Intelligence..........BLOCKED
Activation............BLOCKED
Recommendation........BLOCKED
Readiness.............BLOCKED
Environment...........BLOCKED
Feasibility...........BLOCKED
Package...............BLOCKED
Consumer..............BLOCKED
Executor..............BLOCKED
OrderSend.............BLOCKED
Broker................BLOCKED
Position..............BLOCKED
Restart...............BLOCKED
Recovery..............BLOCKED
====================================

SYSTEM STATUS

DEMO OPERATION NOT VERIFIED
```

## Acceptance decision and evidence handoff

PR225 is **not accepted** by this environment.  The report may be changed to
`DEMO OPERATION VERIFIED` only after all of the following are attached and
reviewed together: raw append-only events, Writer publication captures,
repository inventories/hashes, UUID lineage table, three package byte hashes,
redacted `OrderSend` request/result, broker history and position lifecycle,
three restart transcripts, six failure-injection transcripts, and raw latency
checkpoints.  Every item must refer to the same run ID and baseline.

PR226 must not begin on the strength of this report: its 24–72 hour stability
window is gated on a successful, evidence-backed PR225 Demo certification.
