# V28 Outcome Intelligence Contract

## Authority boundary

Outcome Intelligence is an evidence-only layer after Production Readiness Governance. It observes a
completed trade and preserves its lifecycle and upstream lineage. It has no authority to analyze markets,
generate or alter decisions, construct or mutate risk, send orders, change runtime behavior, promote to
production, learn, train models, or tune thresholds.

Future learning systems **must consume the versioned Outcome Evidence Contract only**. Broker history is
not an authoritative learning input and must not be consumed directly.

## Completed-trade evidence

Exactly one `OutcomeRecord` represents one completed trade. The immutable record binds:

* trade, symbol, direction, entry and exit identity, time, price, and exit reason;
* stop loss, take profit, position size, spread, slippage, commission, swap, gross and net profit;
* initial monetary risk, R multiple, and holding time;
* runtime, market-regime, opportunity, decision, risk, and execution snapshots;
* confidence, Execution Plan, Operational Qualification, and Production Readiness identities.

Net profit is `gross profit + commission + swap`. R multiple is `net profit / initial monetary risk`.
The initial risk must be positive. These are normalization rules, not performance evaluation or learning.

## Identity and replay

Records, lifecycle elements, snapshots, results, registry entries, registry snapshots, and evidence contracts
use domain-separated SHA-256 identities over canonical payloads. Reconstructing the same completed-trade
evidence produces the same identity. Any field or lineage mutation invalidates replay.

The Outcome Registry returns a new immutable snapshot for each append. It rejects duplicate outcome and
trade identities and chains each entry to its predecessor. The `expectancy_dataset` is only an ordered view
of evidence records; it performs no aggregation, inference, learning, scoring, or policy mutation.
