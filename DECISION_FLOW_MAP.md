# DECISION_FLOW_MAP — Runtime Lineage and Participation Governance Flow

## Authoritative lineage
`codex-dev` (single source of truth)

## V28 decision-rebuild approval flow (proposal only)

`Market -> Opportunity -> Positive Edge Verification -> Decision -> Risk -> Publish`

The first and controlling question is: **Does this opportunity have positive
expectancy?** Direction is selected only after the positive-edge verification
passes. `docs/v28/V28_DECISION_PHILOSOPHY.md` and
`docs/v28/V28_EXPECTANCY_FIRST_ARCHITECTURE_ADDENDUM.md` define the required
opportunity, positive-edge, evidence, decision-lineage, and approval contract.

This is not an active runtime path. No implementation work is authorized until
the philosophy document receives explicit approval. V27 remains the current
runtime path below; no V27 filters, cooldowns, waits, score adjustments, patch
stacks, or runtime layers may be added under this directive.

## Governance flow
1. AI room proposes reference patch
2. Codex merges into authoritative code review stream
3. `codex-dev` verification
4. Test validation
5. Approved LIVE promotion

## PR169 rollback orchestration flow
`Runtime Health / Rollback Request`
-> `learning.rollback_orchestration` request, UUID, lineage, manifest, compatibility, and snapshot validation
-> `MANUAL_ONLY` human approval
-> deterministic rollback decision, authorization, plan, package, and append-only audit evidence
-> `Controlled Activation` (outside PR169 authority)
-> registry snapshot and immutable KnowledgeVersion (outside PR169 authority).

PR169 has no Runtime, broker, registry, activation, promotion, or version-mutation capability.

## PR182 governed advisory confidence flow

`PR181 canonical eligibility record / report / snapshot`
-> exact provenance and historical eligibility-snapshot verification
-> deterministic extraction of eligibility completeness, package, registry,
promotion, validation, reason-severity, membership, lineage, and policy-partition evidence
-> policy-bound weighted normalization, deterministic rounding, and advisory banding
-> immutable `ConfidenceRecord` and `RuntimeConfidenceReport`
-> atomic append-only confidence repository and source-context-bound snapshot history
-> future PR183 Governed Advisory Decision-Context Preparation (outside PR182 authority and blocked pending PR182.1 approval and merge).

`CONFIDENCE_EVALUATED` means only that the evidence calculation completed. PR182
does not activate or apply knowledge, rank it for trading, or control strategy,
bias, direction, risk, decision publication, Runtime behavior, or execution.

PR182.1 confirmed and remediated all four consolidated review findings. The
PR180 -> PR181 -> PR182 path now carries and identity-binds the complete
canonical upstream lineage, while eligibility/confidence records reconstruct
their explicitly bound immutable parent artifacts fail-closed. Repository,
snapshot, and report partitions include the inherited PR175 mining and PR177
validation engine/policy/configuration dimensions. No Runtime activation or
trading authority was added; PR183 remains unimplemented and blocked until
PR182.1 is approved and merged.

## Runtime execution path (current)
`bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py`
-> reads `market_state.json`
-> builds directional decision payload
-> applies entry-quality / NOVA / candle / exhaustion / structure / timing / location layers
-> applies V26.4.7 participation restoration
-> applies compatibility/validation layers
-> injects runtime identity metadata
-> atomically writes `decision.json`

## V26.4.7 directional authority chain
1. Hard safety blocks remain final authority.
2. Valid directional bias and score context are preserved through governance layers.
3. Weak momentum becomes a confidence penalty rather than a hard directional erase.
4. Cooldown, low-confidence, and timing waits are represented as finite `WAIT_VALID` recovery states.
5. `WAIT_VALID` timeout releases controlled participation through `EXECUTE_CAUTIOUS`.
6. `TRANSITION_WAIT` has a maximum duration and releases instead of recursively suppressing.
7. Final payload normalization preserves one outcome chain: safety block, finite wait, cautious execution, normal execution, or aggressive execution.

## Migration target (deferred-safe path)
Target file name: `bridge/ai_decision_engine_xauusd_live.py`

Recommended safe migration sequence:
1. Introduce `ai_decision_engine_xauusd_live.py` as thin launcher importing current runtime module.
2. Verify parity in decision outputs and startup identity logs.
3. Update operational launch scripts to point to `_live.py`.
4. Keep previous file as rollback reference until burn-in window passes.

## V26.4.8 intent-to-payload flow update
Final write normalization now includes an explicit intent-to-payload bridge:

`directional ACTION/BIAS`
-> hard-safety check
-> `construct_risk_payload_before_validation()`
-> final payload validation
-> executable `TRADE` or explicit `WAIT_VALID` / hard-safety block

This guarantees controlled participation packets are built before validation, not after validation has already downgraded them.

## V26.5 execution-quality flow update
Directional ideas now pass through an execution-quality core before final confidence and payload validation:

`directional ACTION/BIAS`
-> `ENTRY_LOCATION_SCORE`
-> `directional idea + execution legs`
-> `profit lock ladder metadata`
-> execution confidence
-> risk payload construction
-> final validation
-> executable `TRADE` or explicit quality wait.

The quality core is not a new indicator layer. It reuses existing PA/structure/SR/BB/RSI/MACD/timing fields to answer the execution question: `Is this location still worth entering?`

Leg governance remains one-directional only:
- Leg A scouts the idea.
- Leg B may participate only after pullback/continuation quality improves.
- Leg C is reserved for runner-quality trend expansion.
- All scaling is winner-only; martingale, averaging losers, and hedge architecture remain prohibited.

## V26.5 expectancy-structure repair update
The execution chain is now audited as an authority map, not just a participation map:

`AI DECISION`
-> schema/time/freshness validation
-> entry-quality/NOVA/candle/exhaustion/structure/timing/location scoring
-> legacy strategy blocks converted to confidence penalties when AI authority is valid
-> management alignment and planned RR enforcement
-> final payload validation
-> broker/executor hard safety checks
-> `FINAL ORDER AUTHORITY`.

AI authority is valid only when `decision=TRADE`, bias is BUY/SELL, mode and BB state are schema-valid, heartbeat/market freshness are valid, score edge exists, and no hard safety block is active. In that state, legacy M15/M3 misalignment, M3 timing conflict, NOVA quality rejection, and V17 entry-quality rejection are no longer automatic executor vetoes; they are published as confidence penalties and audit fields.

Final hard veto authority is intentionally limited to:
- stale market data / heartbeat failure
- invalid JSON or invalid schema
- invalid market data
- abnormal spread / liquidity / broker freeze
- duplicate order protection
- catastrophic daily risk limit / hard realized-loss control
- catastrophic hard-risk state

Expectancy structure is enforced before publishing a TRADE payload. SCALP structures must plan at least 1.2R; TREND and runner structures must plan at least 1.5R. TREND + `WALK_UP` / `WALK_DOWN` with score-gap authority prefers `HOLD_TRAIL` instead of silently downgrading into `SCALP_TP`; `SCALP_TP` remains a secondary management mode.

## V26.6 expectancy-repair flow update
The final write path now prioritizes expectancy before signal count:

`directional ACTION/BIAS`
-> existing safety and quality scoring
-> weak-momentum confidence penalty only when hard safety is clear
-> `LATE_ENTRY_SCORE` maturity audit
-> execution confidence
-> trend management enforcement (`TREND` cannot silently publish `SCALP_TP`)
-> graded early participation sizing (`gap=2/3/4` => `25%/50%/100%` risk)
-> risk payload construction and planned RR enforcement
-> `MAX_REALIZED_LOSS_GUARD` metadata
-> final validation
-> executable trade, reduced-size mature-entry trade, or `WAIT_ENTRY_LOCATION`.

This flow keeps existing indicators and classifier structure. It changes execution governance so optimization is measured by expectancy, Average R Win/Loss, runner capture, and realized-vs-planned loss discipline instead of raw signal count.

## V26.6.1 protection-authority flow update
The expectancy repair chain now includes a single protection authority before final payload construction:

`directional ACTION/BIAS`
-> existing safety and quality scoring
-> finite WAIT / cooldown / location protection candidates
-> `Protection Authority Manager`
-> exactly one `ACTIVE_PROTECTION_STATE`; other detected protections are `PENDING`
-> mandatory release metadata (`entry_condition`, `exit_condition`, `maximum_duration`, `maximum_cycles`, `recovery_path`)
-> risk payload construction and final validation
-> executable trade, released cautious participation, or one finite active protection.

This prevents the prior cascade pattern:

`THESIS_REVALIDATION_AFTER_LOSS -> THESIS_DECAY_WAIT -> WAIT_ENTRY_LOCATION -> POST_RUNNER_COOLDOWN -> NO PARTICIPATION`

from becoming recursive. The manager does not remove hard safety; it prevents multiple quality/profit/cooldown protections from all being simultaneously active and unbounded.

## V26.6.1 executor legacy-veto conflict audit update
The single execution authority chain is now:

`AI Decision`
-> `Payload Validation`
-> `Executor broker-safety checks only`
-> `Market / OrderSend`

Executor-side veto classification:
- `HARD_SAFETY_BLOCK`: stale decision, invalid payload, invalid schema, abnormal spread, no liquidity, broker freeze, duplicate order protection, daily risk limit.
- `SOFT_DIAGNOSTIC_PENALTY`: V17 AI quality block, V15 entry block, `analysis_quality` filters, M15/M3 alignment vetoes, legacy participation/cooldown/location/quality gates.

When `decision=TRADE`, `allowed=true`, `entry_allowed=true`, `payload_valid=true`, BUY/SELL bias is valid, and no hard safety block is active, no legacy quality gate may convert the payload to `NO_TRADE`. Legacy quality values remain visible as telemetry (`analysis_quality_diagnostic`, `v17_quality_score_diagnostic`, `legacy_executor_veto_policy`) and may reduce confidence, but they do not override V26 execution authority.

## V26.6.5A executor authority enforcement hotfix
The restored single execution authority chain is:

`AI Decision`
-> `Payload Validation`
-> `Broker Safety`
-> `OrderSend`
-> `Market`

If `decision=TRADE`, `allowed=true`, `payload_valid=true`, and `schema_valid=true`, the executor must not allow legacy strategy filters to terminate execution. V15/V16/V17 entry, AI-quality, hard-block, and M15/M3 alignment findings remain visible as warnings/diagnostics, but they do not own execution authority and may not suppress `OrderSend`.

Only these classes may terminate execution after an AI-approved payload: invalid payload, invalid schema, stale decision, broker freeze, abnormal spread, duplicate order, insufficient margin, market closed, and catastrophic risk state. A validated TRADE that does not call `OrderSend` must emit `EXECUTOR_BUG_NO_ORDERSEND_AFTER_TRADE`. Normal send path logs are `EXECUTOR_FINAL_GATE_PASS`, `ORDER_SEND_ATTEMPT`, and exactly one of `ORDER_SEND_OK` / `ORDER_SEND_FAIL`.

## V26.6.2A no-pause adaptive expectancy flow update
The final write path now includes an emergency expectancy-distribution guard:

`directional ACTION/BIAS`
-> existing safety and quality scoring
-> V26 execution confidence
-> trend management preservation (`TREND + WALK_UP/WALK_DOWN` prefers `HOLD_TRAIL` / `TREND_RUNNER`)
-> `V26.6.2_EXPECTANCY_ENTRY_FILTER`
-> `V26.6.2A_SESSION_LOSS_GOVERNOR` (loss diagnosis + adaptive risk reduction; no mandatory pause)
-> risk payload construction
-> `V26.6.2_LOSS_CAP_AND_PROFIT_LOCK`
-> planned RR enforcement
-> final payload validation
-> executor hard-safety contract.

Emergency distribution rules:
- `score_gap < 3` is `NO_TRADE`.
- `TRANSITION + NORMAL` requires `score_gap >= 4`.
- BB-middle entries require strong RSI and MACD confirmation in the trade direction.
- For `0.01` lot XAUUSD, new TRADE payloads publish `max_realized_loss_usd_001_lot = 1.20` and compress SL distance to that reference cap.
- If floating loss approaches the cap, executor-side trade management should force exit using the published `floating_force_exit_usd_001_lot` / `floating_force_exit_points` fields.
- If profit reaches `+$0.80`, executor-side trade management should move SL to breakeven plus spread using the published breakeven ladder fields.
- If profit reaches `+$1.20`, executor-side trade management should lock at least `+$0.50` using the published lock ladder fields.
- After every loss, classify the loss cause: `LATE_ENTRY`, `EXHAUSTION_ENTRY`, `CHOP_ENTRY`, `REVERSAL_ENTRY`, `SL_TOO_WIDE`, `BE_TOO_TIGHT`, `TREND_THESIS_FAILED`, or `EXECUTOR_MANAGEMENT_FAILURE`.
- Two consecutive losses no longer trigger a mandatory pause. Loss clusters are diagnostic telemetry that trigger thesis revalidation and adaptive size-down.
- Same-direction repeated losses re-check bias, mode, BB state, RSI/MACD context, entry location score, and exhaustion score. Valid thesis continues cautiously; invalid thesis waits for better location or evaluates the opposite thesis.
- After a loss cluster, next participation is reduced-risk Leg A only: no runner, no pyramid, no runner add, no continuation add, and tighter risk cap.
- Current-day drawdown beyond threshold activates `DRAWDOWN_CAUTION_MODE`, not a daily kill switch: reduced size, Leg A only, higher entry-location score, no runner add, and no continuation add. Full stop is reserved for catastrophic hard-risk state.

This layer does not add indicators and does not bypass hard safety. Its purpose is to transform realized expectancy from many small wins plus larger losses into moderate wins plus controlled losses while keeping AI learning and participating with reduced risk.

## V26.6.3 exit / risk asymmetry emergency flow update
The final write path keeps the existing entry engine and adds an exit-first risk asymmetry layer:

`directional ACTION/BIAS`
-> existing safety and quality scoring
-> V26 execution confidence
-> unchanged V26.6.2 expectancy entry filters
-> `V26.6.3_EXIT_RISK_ASYMMETRY_GOVERNOR`
-> risk payload construction
-> hard loss cap / early damage cut / breakeven ladder / profit lock ladder
-> runner damage limit and 30-45 second runner momentum timeout metadata
-> daily emergency risk stop at `<= -$5.00`
-> three-loss extreme caution mode
-> final payload validation
-> executor hard-safety contract.

This update does not add indicators, redesign signal generation, introduce hedging, martingale, or average losing trades. It changes position lifecycle enforcement so big realized losses below `-$2.00` should approach zero under standard `0.01` lot operation.

## V26.6.4 exit authority / leg-aware profit protection flow update
The final write path now ends with an executor-enforceable exit authority manager:

`payload validation / risk construction`
-> `hard loss cap + leg-aware profit ladder publication`
-> `single Exit Authority Manager`
-> `management authority lock`
-> `executor authority contract`
-> `decision.json`.

Exit authority priority is fixed and non-recursive:
`EMERGENCY_EXIT -> HARD_LOSS_CAP -> DAILY_GUARD_RISK_COMPRESSION -> FORCE_SCALP_TP -> LEG_A_SCALP_EXIT -> LEG_B_CONFIRMATION_EXIT -> LEG_C_RUNNER_EXIT`.

If `FORCE_SCALP_TP` owns a position, all downstream fields must treat management as `SCALP_TP`; runner/trail management cannot reactivate underneath that owner. Leg A and Leg B use distinct USD-per-0.01-lot ladders, while Leg C preserves runner intent through structure trail, momentum decay, swing protection, and BB-walk continuity. Daily Guard compresses risk and blocks new entries without converting open losing positions into arbitrary panic closes.

## V26.6.5 execution timing flow update
The final write path now separates directional thesis from executable timing:

`directional ACTION/BIAS`
-> existing safety and quality scoring
-> V26 execution confidence
-> `V26.6.5_EXECUTION_TIMING_LAYER`
-> `ENTRY_WINDOW_SCORE` / `WAIT_ENTRY_WINDOW` or open entry window
-> risk payload construction
-> exit authority / payload validation
-> executor hard-safety contract.

The timing layer is not a new directional classifier. It reuses existing short-term candle/structure/BB/RSI/MACD/pullback/continuation telemetry. If HTF bias is BUY while short-term state shows bearish impulse, lower-high/lower-low structure, BB walk down, negative MACD expansion, or weak RSI recovery, the payload preserves BUY bias but waits with `WAIT_ENTRY_WINDOW`. SELL is handled by mirrored logic. Entry reopens when short-term phase transitions from `PULLBACK` to `RESUMPTION` / `TREND_EXPANSION` through recovery evidence such as pullback maturity, momentum improvement, continuation quality, and BB-walk ending/aligning.

## V26.6.6 expectancy diagnostic + exhaustion / protection flow update
The final write path now adds diagnostic and protective expectancy controls without reducing the normal signal cadence:

`real BUY/SELL signal`
-> `shadow opposite-direction audit record (non-live)`
-> existing execution timing / location scoring
-> `V26.6.6_EXHAUSTION_PROTECTION` (`WAIT_ENTRY_WINDOW`, reduced size, no-runner scalp-only, or allow)
-> `same-direction loss-chain direction pause` (pause losing direction only after 3 losses)
-> `profit protection publication` (`+$0.50` BE, `+$0.80` small-profit lock)
-> `runner allowed only after primary leg protected`
-> executor authority contract.

The shadow audit answers whether loss clusters are caused by wrong direction or by poor timing/exit management. It is telemetry only and cannot place opposite live trades.

## V26.6.7 trade autopsy evidence flow update
Closed-trade analytics now run after execution and do not feed back into live entry or exit authority:

`closed RP trade in trade_memory.csv`
-> `TRADE AUTOPSY ENGINE`
-> one CSV row per closed trade with identity, entry context, exit context, MFE/MAE, realized R, profit give-back, shadow-opposite audit, and evidence fields
-> daily JSON summary with win/loss distribution, expectancy, MFE capture, MAE containment, shadow-opposite result, and root-cause ranking by capital damage.

The autopsy engine is evidence-only. It cannot publish live trade decisions, cannot place opposite trades, cannot reduce entry frequency, cannot add indicators, and cannot change executor or exit authority. Its only purpose is to identify which loss bucket is causing the largest capital damage after 100-300 closed trades.

## V27 trade management dashboard flow update
The runtime is now split into independent subsystems:

`AI Decision Engine`
-> direction / bias / entry timing / market mode / position classification / initial risk
-> `POSITION CREATED`
-> `Trade Management Dashboard runtime profile load`
-> dashboard-configured SL, breakeven, trailing, profit-lock, runner, time-exit, partial-exit parameters
-> `Exit Authority Manager`
-> single effective exit owner
-> broker / executor.

Dashboard profile loading order:
1. Load embedded backward-compatible defaults.
2. Load `trade_management_dashboard.json` if present.
3. Resolve `active_profile`.
4. Overlay `dashboard_profiles/<active_profile>.json` if present.
5. Publish `trade_management_dashboard`, `dashboard_active_profile`, schema version, and source/fallback metadata to `decision.json`.

No V27 dashboard profile may mutate AI direction, bias, entry timing, signal generation, or market classification.

## PR173 outcome attribution flow

`Immutable Runtime / Learning Evidence` -> `learning.outcome_attribution` -> offline deterministic, advisory-only descriptive feature, indicator, risk, regime, context, success/failure, and sample-support attribution -> immutable report. This is non-causal analytical evidence and has no Runtime, Registry, promotion, activation, rollback, or execution authority. `learning.analytics` separately retains lineage, conflict, stability, and governance analytics authority.

## PR173 / PR174 offline eligibility flow
`Immutable evidence -> PR173 outcome attribution -> PR174 structural validation, identity/outcome/replay gates, and sample sufficiency -> immutable advisory eligibility report -> potential future offline pattern-mining stage.` PR174 performs no mining, learning, promotion, activation, registry, runtime, or broker action.

## PR175 offline pattern-mining flow

`PR174 eligible policy report + content-addressed ApprovedPatternMiningEvidenceEnvelope (version + UUID + digest + policy/attribution/replay provenance + outcome contract + unique canonical samples) -> strict mining configuration + normalization -> deterministic grouping -> support/expectancy/confidence -> provenance-complete advisory CandidatePattern + envelope/config-bound PatternMiningReport -> future PR176 Pattern Memory.` Duplicate sample identities are forbidden and mining configuration is part of replay identity. PR175 never creates, modifies, infers, promotes, activates, or publishes Runtime evidence and has no Registry, broker, or execution authority.

## PR176 offline Pattern Memory flow

```text
PR175 PatternMiningReport
        |
        v
PR176 Pattern Memory validation
        |-- full provenance retention
        |-- canonical governance identity
        |-- content-addressed memory UUID
        |-- immutable full-record digest
        |-- append-only persistence
        |-- historical grouping indexes
        `-- chained repository snapshot integrity
        |
        v
Future governed validation/promotion stages
```

PR176 owns pattern history storage, memory identity, append-only persistence, immutable indexing, replay verification, and repository snapshot reporting. It does not own learning, pattern approval, pattern promotion, activation, knowledge promotion, Registry or Runtime mutation, decision publication, broker safety, `OrderSend`, position management, or execution authority. `STORED` is a persistence state only and never means runtime-active; Pattern Memory is historical evidence only.

## PR177 governed Pattern Validation flow

```text
PR176 Pattern Memory
        |
        v
PR177 Pattern Validation
        |-- complete provenance verification
        |-- source replay and snapshot verification
        |-- versioned historical-quality configuration
        |-- statistical consistency classification
        |-- domain-separated validation identity
        |-- append-only validation history and snapshot chain
        `-- immutable advisory-only reporting
        |
        v
Future separately governed promotion stages
```

`STATISTICALLY_CONSISTENT` means only that the versioned PR177 historical checks passed. Statistical consistency is not pattern approval, and PR177 never authorizes runtime usage. PR177 owns historical validation, validation identity, replay verification, validation history, and repository reporting. It has no learning, approval, promotion, activation, Runtime or Registry mutation, decision-publication, broker-safety, `OrderSend`, position-management, or execution authority.

## PR178 governed Promotion Policy Assessment flow

```text
PR176 Pattern Memory
        |
        v
PR177 Pattern Validation
        |
        v
PR178 Promotion Policy Assessment
        |-- exact PR177 artifact, snapshot, repository, and configuration binding
        |-- complete PR176/PR177 provenance retention
        |-- immutable policy and engine identities
        |-- anti-downgrade threshold verification
        |-- neutral criteria assessment
        |-- append-only replay-verifiable history
        `-- policy-bound repository snapshot chain
        |
        v
Future separately governed Registry Admission stage
```

PR178 owns promotion-policy identity, criteria assessment, assessment identity, replay verification, append-only assessment history, repository snapshots, and advisory-only reporting. It does not own Knowledge Registry publication or mutation, pattern approval, registration or activation, Runtime activation or mutation, decision publication, trading bias or direction, broker safety, `OrderSend`, position management, exit authority, or execution authority.

`POLICY_CRITERIA_MET` means only that the immutable PR178 policy criteria were satisfied. It does not mean promoted, published, registered, activated, approved for Runtime use, or tradable.

## PR179 advisory Knowledge Registry flow

`PR176 Pattern Memory -> PR177 Pattern Validation -> PR178 Promotion Policy Assessment -> PR179 Advisory Knowledge Registry Admission -> PR180 Advisory Runtime Knowledge Packaging -> future PR181 Governed Knowledge Selector`.

PR179 records offline historical governance metadata only. It owns its admission-policy and record identities, complete PR178 provenance, replay checks, append-only history, snapshots, repository integrity, and advisory reports. It does not own Runtime activation or consumption, inference authority, pattern activation or execution approval, trading bias or direction, decision publication, broker safety, `OrderSend`, position management, exit authority, or execution authority. `ADVISORY_ENTRY_RECORDED` has no operational meaning.

## PR180 governed advisory Runtime knowledge packaging flow

`PR179 canonical Knowledge Registry -> registry/snapshot/repository/replay/governance verification -> immutable advisory RuntimeKnowledgePackage -> future PR181 selector`.

PR180 is a fail-closed verification and advisory packaging boundary only. It owns exact canonical PR179 report/record binding, historical snapshot membership verification, complete governance provenance retention, packaging-policy and package identities, replay verification, append-only history, and package-repository integrity. It reads no raw trades, mining, Pattern Memory, Pattern Validation, or Pattern Promotion repositories. It has no Runtime decision use, selection, ranking, weighting, activation, inference, confidence, bias, scoring, direction, risk, decision-publication, position-management, broker, exit, or execution authority, and the existing Runtime Decision Engine remains unchanged. `ADVISORY_PACKAGE_PREPARED` denotes preparation for a future separately governed stage only.

## PR181 governed advisory knowledge eligibility flow

`PR180 Advisory Runtime Knowledge Packaging -> PR181 canonical source and exact snapshot-membership verification -> immutable advisory eligibility evidence and state -> future PR182 Governed Confidence Evaluation`.

`evaluate_eligibility()` records advisory eligibility only. It does not activate, apply, weight, rank, score, or authorize Runtime knowledge. PR181 owns canonical source verification, exact snapshot membership, eligibility-policy identity, eligibility evidence and state retention, replay protection, append-only history, and repository/snapshot/report integrity. It never owns activation, application, confidence scoring, inference, trading bias, direction, risk, decision publication, broker safety, `OrderSend`, position management, exit authority, or execution.

## PR182 / PR183 governed advisory Decision Context flow

`PR181 Eligibility -> PR182 Confidence Evaluation -> PR183 canonical confidence provenance, repository, snapshot, and policy verification -> immutable advisory DecisionContext -> future PR184 Decision Intelligence Evaluation.`

PR183 prepares context only. `CONTEXT_PREPARED` has no trading or operational meaning and cannot influence Market Analysis, strategy, bias, direction, risk, decision publication, Runtime or knowledge activation, broker safety, `OrderSend`, position management, exit authority, or execution. Only future PR184 may consume a `DecisionContext` to derive advisory Decision Intelligence.


## PR184 governed advisory Decision Intelligence flow

`PR183 Decision Context -> PR184 canonical provenance, repository, snapshot, policy, and engine verification -> immutable advisory Decision Intelligence -> future PR185 Decision Recommendation.`

PR184's quality, reliability, consistency, and recommendation-review fields are advisory evidence only. `DECISION_INTELLIGENCE_READY` is not BUY, SELL, HOLD, trade approval, publication, activation, or execution approval. Only future PR185 may consume Decision Intelligence, and PR185 remains advisory-only.

## PR185 governed advisory Decision Recommendation flow

`PR184 Decision Intelligence -> PR185 canonical provenance, repository, snapshot, policy, and engine verification -> immutable advisory Recommendation.`

PR185 outputs `REJECTED`, `INSUFFICIENT_RECOMMENDATION_EVIDENCE`, or `RECOMMENDATION_READY`, classified as `READY_FOR_DECISION`, `NOT_READY`, `INSUFFICIENT_EVIDENCE`, `MANUAL_REVIEW`, or `REJECTED`. Every result remains advisory: it is not BUY, SELL, HOLD, a trading decision, or execution approval.

## PR186 governed advisory Execution Readiness flow

`PR185 Recommendation -> PR186 canonical provenance, repository, snapshot, policy, engine, replay, and lineage verification -> immutable advisory Execution Readiness -> future PR187 Execution Environment Intelligence.`

`EXECUTION_READY_FOR_ENVIRONMENT_CHECK` confirms only internal advisory-pipeline completeness. It is not BUY, SELL, trade approval, decision publication, runtime activation, broker communication, `OrderSend`, or execution approval. PR187 may assess environment quality separately; execution authority remains exclusively in the MT5 Executor.

## PR187 governed advisory Execution Environment Intelligence flow

`PR186 Execution Readiness -> PR187 canonical provenance, repository, snapshot, policy, engine, replay, and lineage verification -> immutable advisory Execution Environment -> future PR188 Execution Feasibility.`

PR187 evaluates environment quality only. `ENVIRONMENT_READY_FOR_FEASIBILITY` is
not BUY, SELL, trade approval, decision publication, runtime activation, broker
communication, `OrderSend`, or execution approval.

## PR188 governed advisory Execution Feasibility flow

`PR186 Execution Readiness + PR187 Execution Environment -> PR188 exact record, repository, snapshot, policy, engine, replay, and cross-stage lineage verification -> immutable advisory Execution Feasibility -> future PR189 Execution Package Assembly.`

`EXECUTION_FEASIBLE` records advisory prerequisite completeness only. It is not BUY, SELL, trade approval, decision publication, runtime activation, broker communication, `OrderSend`, or execution approval.

## PR189 governed advisory Execution Package Assembly flow

`PR186 Execution Readiness + PR187 Execution Environment + PR188 Execution Feasibility -> PR189 exact repository, snapshot, provenance, policy, engine, replay, and lineage verification -> immutable advisory Execution Package -> PR190 canonical immutable consumer interface.`

`PACKAGE_READY` records package assembly only. It is not BUY, SELL, execution
approval, decision publication, runtime activation, broker communication,
`OrderSend`, or execution authority.

## PR190 governed advisory Execution Package Consumer flow

`PR189 immutable Execution Package + canonical package snapshot -> PR190 fail-closed canonical load, UUID, SHA-256, snapshot, version, and replay verification -> immutable in-memory ExecutionPackage for a downstream consumer.`

PR190 adds no evaluation stage and produces no repository artifact, advisory
recommendation, or execution authorization. The proposed validation gateway is
withdrawn. Invalid or missing input fails closed without recovery or repair, and
execution authority remains exclusively inside the MT5 Executor.

## PR191 / PR192 production integration flow

`PR190 immutable ExecutionPackage -> PR191 immutable ExecutionConfidenceContext -> V26 Runtime -> PR192 canonical immutable ExecutionContext -> PR193 atomic publication -> PR194 MT5 Executor consumer`.

PR192 is the only Runtime-to-Executor payload boundary. Its exact canonical
schema exposes execution-facing metadata, not an `ExecutionPackage`, confidence
implementation, strategy object, or governance artifact. The Executor validates
contract version, engine version, replay identity, UUIDs, canonical encoding,
and payload integrity before accepting the complete context. Any failure rejects
the whole payload without repair, fallback, or partial loading. Contract
acceptance itself does not generate BUY or SELL and does not communicate with a
broker, execute a trade, manage a position, or control an exit.

PR194 reads only `execution_context.json` and returns an immutable context only
after exact canonical, integrity, identity, version, timestamp, advisory, and
field-set validation. Any missing or invalid publication fails closed without
fallback, repair, or partial acceptance. It does not read governance, Runtime,
confidence, package, or strategy objects and adds no execution behavior.

## PR195 governed Executor activation flow

`PR194 accepted immutable ExecutionContext + Runtime READY -> PR195 one-shot activation authorization -> existing MT5 Executor lifecycle`.

Any consumer, context, contract, or Runtime-state failure transitions the
activation lifecycle to `REJECTED`; it cannot fall back to a legacy trigger.
PR195 starts but does not implement the Executor. All broker safety, `OrderSend`,
position, stop, target, and exit behavior remains in the existing Executor.

## PR196 production execution wiring flow

`Python Runtime values -> PR193 publication in configured MT5 Common Files -> PR194 exact-file consumption -> Runtime READY -> PR195 one-shot activation -> existing installed MT5 Executor`.

This is the only production startup path. Any failure ends the lifecycle without starting MT5 and without a legacy trigger. PR196 only composes the approved boundaries and introduces no governance, Runtime, or execution layer.

## PR201 live outcome capture flow

`Decision -> ExecutionContext -> optional publication -> consumer acceptance -> activation -> OrderSend timestamp -> broker-confirmed order/deal/position -> position close -> immutable LiveOutcomeRecord`.

PR201 observes only already-completed broker evidence. It validates the complete identity and UTC timestamp sequence and atomically appends one canonical, integrity-bound record. Capture cannot influence any stage it observes and has no analytics, attribution, learning, broker, order, position, exit, or execution authority.

## PR203 completed-trade event flow

`Broker confirms trade closed -> production host creates one CompletedTradeEvent -> passive production outcome integration -> immutable live outcome capture -> operational evidence repository`.

Broker-specific completion objects do not cross the host boundary. Duplicate or invalid events fail closed without affecting execution.

## PR206 pattern discovery flow

`PR205 OutcomeAttribution + exact PR203 CompletedTradeEvent + exact PR201 LiveOutcomeRecord`
-> source integrity, lineage, replay, duplicate, and sample-sufficiency checks
-> deterministic descriptive aggregation
-> immutable SHA-256-bound `Pattern`
-> atomic append-only Pattern Repository
-> future knowledge qualification.

This is an observation-only post-completion flow and the sole producer of
candidate operational knowledge. It performs no prediction, recommendation,
optimisation, governance action, Runtime change, broker action, or execution.
