# PR155 Promotion Decision Engine

`learning.promotion_decision` is a deterministic, read-only advisory boundary. It consumes only a caller-supplied Qualification Report, Control Plane Snapshot, and explicit `PromotionPolicyConfig`. It does not import or access repositories, governance, lifecycle, analytics, policy engines, runtime, executors, brokers, or promotion authority.

`PromotionDecisionEngine.evaluate()`, `decision()`, `explain()`, and `summary()` produce an immutable `PromotionDecisionReport`; none writes or promotes. Persistence is explicit through `PromotionDecisionRepository`, which atomically stores append-only reports at `learning_data/promotion_decision/decision_<uuid>.json`.

The engine approves only `QUALIFIED` reports meeting the score threshold, with a healthy Control Plane and repository, no active duplicate/lock, allowable conflict severity, an open promotion window, no freeze window, and no cooldown. Identical supplied inputs produce the same report UUID and content.
