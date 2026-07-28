# PR236 Execution Package

`ExecutionPackageAssembler` is the sole Python boundary from one immutable read
of `decision.json` to `execution_package.json`. It copies strategy, risk, price,
and management facts without recalculation. The package has exactly the 19
canonical fields specified by PR236 and a new execution UUID; decision UUID,
market source UUID, and market sequence are preserved as lineage.

Construction is intentionally separate from the existing runtime and executor.
The executor remains responsible for broker validation and `OrderSend`.
