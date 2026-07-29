# PR270 Outcome Analytics Engine

PR270 adds a deterministic, offline analytics boundary over validated PR269
Learning Evidence. It reports expectancy, win/loss/breakeven distribution,
sequence-sensitive net and R-multiple drawdown, regime and opportunity
performance, confidence calibration, and descriptive loss classification.

Every report is content-addressed, schema-versioned, policy-bound, and tied to
both its source Learning Dataset and Learning Evidence identities. Replaying the
same evidence produces the same report; reordered or altered evidence does not.

The engine is analytics only. It performs no training, creates no improvement
candidate, mutates no runtime state, grants no production authority, and has no
broker or execution dependency. Missing regime or opportunity dimensions are
reported as `UNKNOWN` rather than inferred.
