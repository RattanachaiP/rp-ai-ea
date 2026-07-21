# V27.7 Executor Integration Report

## Ownership and contract

`runtime.executor.Executor` is the final execution authority only. Its sole
runtime input is one immutable `bridge.decision_writer.WriterReadResult`; it
does not open or re-read `decision.json`. The Writer bridge freezes the
payload recursively before it reaches a consumer. Execution requires the
published flags `fail_safe == false`, `executable == true`,
`entry_permission == true`, a literal `BUY` or `SELL` direction, and an
`ALLOW_START` or `ALLOW_SCALE` construction action. No confidence,
probability, score, expected-value, or other Brain field is inspected.

The upstream `DecisionPackage` owns the fully constructed instruction:
`symbol`, `volume`, `entry_price`, `stop_loss`, and `take_profit`. The Writer
Adapter validates and copies those values unchanged to `RuntimeDecisionPayload`.
The Decision Publisher persists them in `decision.json`, and the Writer bridge
requires and type-validates them before creating its immutable snapshot. An
executable package without all five values is made fail-safe; Executor never
fills in a missing value.

## Broker safety and submission

`runtime.broker_safety.BrokerSafety` is isolated from decision logic and checks
only the pre-existing execution instruction and broker facts: symbol,
permission, market availability, min/max/step lot validity, SL/TP geometry,
and free versus required margin. It rejects without calling `send_order`.
`MT5ExecutionInterface` isolates the eventual MT5 adapter. The executor adds
the immutable execution ID to its logs and order comment; broker result ticket
and result code are retained in `ExecutionResult` for trade-journal and MT5
diagnostics adapters.

## Duplicate, retry, and failure behavior

Every `execute` call allocates a unique opaque execution ID before validation.
Accepted sequence IDs are remembered for the executor lifetime, so a
publication is never submitted twice. A retryable broker response may be
retried only within that same execution cycle when the broker explicitly
reports `CONFIRMED_REJECTED_RETRYABLE`, proving that no order was executed.
Retries always use the same frozen instruction and execution ID; the configured
retry count bounds this behavior. `AMBIGUOUS` results, send exceptions, and
malformed broker responses return `EXECUTION_OUTCOME_UNKNOWN` without a retry;
production reconciliation must search by execution ID, ticket, and comment.
All contract, safety, and broker failures return an auditable result, log the
rejection, and leave the original snapshot untouched.

## Non-responsibilities and production considerations

The executor does not generate direction, interpret `decision`, calculate an
executable payload, override permissions, or import Brain, Writer Adapter, or
Decision Publisher modules. Production wiring must provide a real
`MT5ExecutionInterface`, persist sequence/execution journal state across
restart where duplicate protection must survive restarts, and pass only writer
bridge-accepted snapshots containing a publisher-owned order instruction.
