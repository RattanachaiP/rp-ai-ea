# PR155 Promotion Decision Engine

`learning.promotion_decision` is a deterministic, read-only advisory boundary. It consumes only a caller-supplied immutable Qualification Report, Control Plane Snapshot, and explicit `PromotionPolicyConfig`. It does not promote knowledge and does not import or access repositories, governance, lifecycle, analytics, policy engines, runtime, executors, brokers, or a future Promotion Authority.

## Architecture position

```text
Qualification Engine
        ↓
Promotion Decision Engine (PR155, advisory only)
        ↓
Promotion Authority (future, mutating authority)
```

PR155 is not the Promotion Authority. `PROMOTE` means that the supplied evidence satisfies advisory policy; it is not an execution instruction.

## Evidence binding

The engine fails closed unless:

- the Control Plane snapshot digest matches its canonical contents;
- the Qualification Report satisfies its complete immutable contract;
- `qualified=True`, `status=QUALIFIED`, score bounds, and empty failed/unknown checks agree;
- the Qualification Report knowledge UUID matches exactly one snapshot entry;
- the Qualification Report control-plane digest matches the verified snapshot digest;
- health, repository, duplicate, lock, and conflict evidence are structurally valid.

Duplicate detection is semantic, using a candidate promotion/semantic/pattern/lineage key. An unrelated ACTIVE knowledge item does not block promotion. Promotion locks are candidate-scoped and must explicitly declare whether they are active.

## Deterministic temporal policy

Temporal decisions use only the timezone-aware `evaluation_timestamp` supplied in `PromotionPolicyConfig`. Optional `promotion_window_start`, `promotion_window_end`, `freeze_until`, and `cooldown_until` are evaluated against that timestamp. The engine never reads the wall clock.

Decision precedence is explicit:

1. malformed, missing, or conflicting evidence → `MANUAL_REVIEW / BLOCKED`;
2. permanent policy failure → `REJECT / DENIED`;
3. temporary temporal gate → `DEFER / WAITING`;
4. all checks satisfied → `PROMOTE / APPROVED`.

## Persistence

`PromotionDecisionEngine.evaluate()`, `decision()`, `explain()`, and `summary()` never write. Persistence is explicit through `PromotionDecisionRepository`, which atomically stores immutable append-only reports at:

```text
learning_data/promotion_decision/decision_<uuid>.json
```

Identical supplied artifacts and policy produce the same report UUID and content.