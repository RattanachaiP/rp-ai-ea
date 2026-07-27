# PR226 Failure Injection Report

**Result: FAIL — required operational injections not observed.**

| Injection | Required outcome | Observation |
|---|---|---|
| Missing `market_state.json` | Explicit rejection; no downstream order | MISSING |
| Stale heartbeat | Fail closed; no downstream order | MISSING |
| Sequence rollback | Reject rollback; no replay | MISSING |
| Duplicate package | Reject duplicate; exactly one authority | MISSING |
| Invalid digest | Reject before execution | MISSING |
| Corrupted JSON/UTF-8 | Reject; no cached substitution | MISSING |
| Broker rejection | Record exact response; invent no position | MISSING |

The absence of undefined behavior cannot be established without the raw
injected inputs, rejection events, zero-order proof, and recovery events.

