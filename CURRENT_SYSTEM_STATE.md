# CURRENT_SYSTEM_STATE — V26.6.2A No-Pause Adaptive Expectancy Fix

Date: 2026-06-12 (UTC)
Authoritative branch policy: `codex-dev`

## PR182 governed advisory confidence evaluation — IMPLEMENTED, PENDING ACCEPTANCE

- Architecture: `PR182`; module: `learning.runtime_confidence`; component: Governed Advisory Confidence Evaluation Engine.
- `evaluate_confidence()` accepts only canonical PR181 eligibility records, reports, and snapshots, resolves their exact historical snapshot membership, and evaluates nine explicit governance-evidence dimensions under a complete deterministic scoring policy.
- Confidence records retain dimension states, raw values, normalized scores, weights, contributions, reasons, confidence bands, the complete PR181/upstream lineage, and exact source-artifact, repository, and snapshot bindings. No market-performance, profitability, expectancy, or execution evidence is invented.
- `CONFIDENCE_EVALUATED` means only that the deterministic advisory calculation completed. PR182 does not activate or apply knowledge, rank knowledge for trading, or control strategy, bias, direction, risk, decision publication, Runtime behavior, broker operations, position management, or execution.
- Confidence history is canonical, atomic, append-only, replay-safe, policy-partitioned, and protected by deterministic identities and a digest-linked snapshot chain under `learning_data/runtime_confidence/`.

## PR181 governed advisory knowledge eligibility — ACTIVE

- Architecture: `PR181`; module: `learning.runtime_selection`; component: Governed Advisory Knowledge Eligibility Selector.
- `evaluate_eligibility()` records advisory eligibility only. It consumes only canonical PR180 packages, snapshots, and packaging reports and retains their complete governance partition, lineage, evidence, and exact snapshot membership.
- It emits immutable advisory-only eligibility artifacts and reports into an atomic append-only, replay-safe repository with chained snapshot history. `ELIGIBLE_FOR_CONFIDENCE_EVALUATION` means only eligible for future PR182 governed confidence evaluation; it never means active, applied, confidence-approved, decision-eligible, tradable, or execution-authorized.
- PR181 owns canonical source verification, exact snapshot membership, eligibility-policy and state identity, evidence retention, replay protection, append-only history, and repository/report integrity. It has no activation, application, ranking, weighting, confidence scoring, inference, trading bias, direction, risk, Registry mutation, Runtime behavior, decision-publication, broker, `OrderSend`, position-management, exit, or execution authority.

## PR175 offline pattern mining — ACTIVE

- Architecture: `PR175`; module: `learning.pattern_mining`; component: Offline Pattern Mining Engine.
- PR175 consumes an eligible PR174 policy report together with a content-addressed, immutable `ApprovedPatternMiningEvidenceEnvelope`. The envelope binds version, deterministic UUID/digest, policy/attribution/replay provenance, outcome contract, sample count, and canonically ordered unique sample identities; duplicates and tampering fail closed.
- Strict mining configuration and its digest are part of replay identity. Candidates retain complete source provenance, while reports retain the exact evidence-envelope and configuration identities.
- It produces immutable, deterministic, advisory-only `CandidatePattern` artifacts and append-only mining reports. It never creates, modifies, infers, promotes, activates, or publishes Runtime evidence and has no Registry, broker, or execution authority.

## PR169 governed knowledge rollback orchestration — ACTIVE

- Architecture: `PR169`; module: `learning.rollback_orchestration`; component: Governed Knowledge Rollback Orchestration Engine.
- The layer validates rollback requests, immutable manifests, compatibility, registry snapshots, policy, manual approval, deterministic replay identity, and expiration before it emits an authorization package.
- It is evidence-only: it never modifies Runtime, the Active Knowledge Registry, or an existing KnowledgeVersion. Atomic append-only artifacts are stored below `learning_data/rollback_orchestration/`.

## V28 mandatory thinking-model rebuild — proposal state

- V27 is not to be repaired or incrementally improved for this directive.
- The V28 replacement philosophy is documented, pending approval, in
  `docs/v28/V28_DECISION_PHILOSOPHY.md` and its mandatory architecture addendum
  `docs/v28/V28_EXPECTANCY_FIRST_ARCHITECTURE_ADDENDUM.md`.
- No implementation is authorized by this state update. In particular, no new
  filters, cooldowns, waits, score adjustments, patch stacks, or runtime layers
  may be added before explicit approval of the V28 decision philosophy.
- V27 remains the active runtime while the proposed V28 philosophy is reviewed.

## Governance posture
- Single authoritative runtime lineage must be maintained on `codex-dev`.
- AI-room patch chains are reference inputs only and are not runtime authorities.
- Required promotion sequence: `AI ROOM -> CODEX MERGE -> codex-dev verification -> TEST -> LIVE promotion`.
- Architecture authority: V26.4.6 Recursive Participation Suppression Fix remains the baseline; V26.4.8 restores controlled participation by forcing valid risk-payload construction before final validation.

## Current repository audit snapshot
- Active runtime engine file in repository: `bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py`.
- No `bridge/ai_decision_engine_xauusd_live.py` runtime alias file exists yet.
- Runtime identity metadata is embedded and exported to `decision.json` on every write:
  - `runtime_branch`
  - `arch_version`
  - `build_tag`
  - `runtime_signature`

## V26.4.7 participation restoration state
- Weak NOVA trend-momentum vetoes are converted into confidence penalties when directional authority, payload validity, market freshness, and hard safety checks remain valid.
- `WAIT_VALID` is finite. A directional wait lifecycle tracks `wait_valid_cycles` and releases to `EXECUTE_CAUTIOUS` after `WAIT_TIMEOUT_CYCLES`.
- `TRANSITION_WAIT` is finite. Persistent weakening tracks `transition_decay_count` and auto-releases after `TRANSITION_WAIT_MAX_CYCLES` instead of becoming a permanent soft lock.
- Participation release fields now explain recovery decisions:
  - `participation_release`
  - `participation_release_reason`
  - `wait_valid_cycles`
  - `wait_timeout_cycles`
  - `transition_wait_max_cycles`
  - `transition_wait_released`

## Safety posture retained
Hard safety remains authoritative and was not downgraded:
- stale market-state protection
- payload/schema validation
- invalid market data protection
- abnormal spread / liquidity / broker freeze protection
- max realized loss cap and catastrophic hard-risk controls

## Deferred expectancy review
Participation restoration intentionally comes before scaling. Before increasing participation size/frequency, review:
- SL sizing
- break-even timing
- trailing behavior
- runner enablement
- profit protection
- average win vs. average loss

## V26.4.8 intent-to-payload execution fix
- Directional `TRADE` intent is now normalized through `construct_risk_payload_before_validation()` immediately before final payload validation.
- A BUY/SELL `TRADE` can no longer reach `validate_final_decision_payload()` with `SL=0` / `TP=0` when a positive `entry_price` / `bid` exists and no hard safety block is active.
- If SL/TP construction cannot be completed because entry context is missing, validation emits controlled `WAIT_VALID` with explicit `risk_payload_construction_reason` instead of silently publishing malformed execution payload.
- Weak NOVA trend momentum remains a confidence penalty path; directional bias, action, scores, and cautious scalp management are preserved when hard safety remains clear.
- Strong `TRANSITION+NORMAL` score dominance (`score_gap >= 4`) treats small RSI misses as `rsi_soft_penalty_only` and allows cautious scalp execution when MACD is not strongly opposite.
- Fast participation override now recognizes preserved BUY/SELL intent in TREND/TRANSITION NORMAL contexts instead of returning `FAST_PARTICIPATION_NOT_TRADE` as a contradiction to participation recovery.

## V26.5 execution quality core upgrade
- Runtime authority advances to `V26.5 | execution-quality-core-upgrade` while keeping `codex-dev` as the single authoritative lineage.
- Execution evaluation now requires `Direction + Entry Quality + Position Construction + Profit Extraction` instead of direction-only participation.
- `ENTRY_LOCATION_SCORE` is a first-class decision field. It rewards fresh breakout/walk context, healthy pullbacks, continuation return, and directional dominance; it penalizes exhaustion, extreme RSI, MA50 distance, BB overextension, late expansion entry, and reversal proximity.
- Poor entry location is treated as a finite quality wait (`WAIT_ENTRY_LOCATION` / `WAIT_VALID`) rather than a malformed or direction-erasing payload.
- Decision payloads now publish a directional idea with multi-leg construction metadata:
  - Leg A: Scout Entry / scalp profit bank.
  - Leg B: Confirmation Entry / pullback continuation participation.
  - Leg C: Continuation Entry / runner capture.
- Scaling policy is explicit: scale into winners only, no martingale, no averaging losers, and no buy+sell hedge architecture.
- Profit extraction metadata now includes a profit-lock ladder concept: +100 points lock +50, +200 lock +100, +300 lock +200.
- Trade-memory analysis now reports daily expectancy metrics: Win Rate, Average Win, Average Loss, Profit Factor, Expectancy, Average Holding Time, and Runner Capture Rate.

## V26.5 expectancy-structure repair
- Legacy quality paths that previously acted as hidden executor vetoes now defer to AI authority when `decision=TRADE`, bias/mode/BB/schema/heartbeat are valid, and hard safety is clear.
- M15/M3 misalignment and M3 timing conflicts are timing refinements with explicit confidence penalties instead of trade annihilation layers.
- NOVA and V17 entry-quality rejections are softened to penalty/audit fields under valid AI authority; only stale data, invalid payload/schema, abnormal spread/liquidity/freeze, duplicate protection, daily risk, and catastrophic risk remain hard final veto classes.
- Trend-walk management now preserves or upgrades runner intent: `TREND + WALK_UP/WALK_DOWN + score_gap >= 4` prefers `HOLD_TRAIL`, with `SCALP_TP` demoted to a secondary mode.
- Planned reward/risk is calculated and enforced before final payload validation: SCALP requires at least 1.2R, while TREND/runner structures require at least 1.5R.

## V26.6 expectancy repair program
- Runtime authority advances to `V26.6 | expectancy-repair-program` under the same `codex-dev` lineage.
- Trend management is now enforced after confidence recovery and final schema normalization: `MODE=TREND` may not publish `SCALP_TP` unless explicit downgrade metadata exists. Silent trend scalps are upgraded to `HOLD_TRAIL` or `TREND_RUNNER` to preserve asymmetric reward capture.
- Early participation is graded by score gap without increasing total risk: gap 2 publishes 25% risk, gap 3 publishes 50% risk, and gap 4+ publishes 100% risk through `risk_fraction` / `position_size_multiplier` fields.
- Loss compression metadata is published on every executable trade: planned SL risk points, max realized loss guard at 1.05R, risk budget fraction, and loss-compression policy fields.
- Late entry scoring now explicitly tracks RSI compression after expansion, BB overextension, MA50 distance, exhausted MACD expansion, and expansion candle count. High scores wait for location reset; elevated scores reduce size.
- Expectancy analytics now report Average R Win, Average R Loss, realized-vs-planned loss ratio, loss-over-plan count, and max loss vs plan in addition to daily expectancy metrics.

## V26.6.1 pre-merge governance safety review
- Runtime authority advances to `V26.6.1 | expectancy-emergency-repair` for protection-cascade control while preserving the V26.6 expectancy repair concept.
- `ACTIVE_PROTECTION_STATE` is now a required decision payload field managed by the Protection Authority Manager.
- Only one protection state may be `ACTIVE` at a time across `SESSION_PROFIT_PROTECTION`, `DAILY_PEAK_DRAWDOWN_PROTECTION`, `THESIS_REVALIDATION_AFTER_LOSS`, `THESIS_DECAY_WAIT`, `POST_RUNNER_COOLDOWN`, and `WAIT_ENTRY_LOCATION`; any additional detected protection becomes `PENDING` instead of stacking recursively.
- Every governed protection publishes an entry condition, exit condition, maximum duration, maximum cycles, and recovery path in `protection_states`.
- WAIT-like protections are finite: `THESIS_DECAY_WAIT` releases on directional recovery / timeout, and `WAIT_ENTRY_LOCATION` releases on location recovery / timeout to controlled cautious participation when directional authority remains valid.
- Monitoring fields now include `protection_activation_count`, `protection_duration_sec`, `protection_duration_cycles`, `opportunity_block_count`, `time_to_recovery_sec`, `protection_pending_states`, `protection_timeout_released`, and `protection_recovery_released`.
- The 72+ hour observation window must evaluate whether protection states improve expectancy or create participation starvation V2 by comparing protection metrics with expectancy, profit factor, average win/loss, and opportunity-block counts.

## V26.6.1 executor legacy-veto audit update
- Executor-side terminal authority is now explicitly constrained to hard safety only: stale decision, invalid payload/schema, abnormal spread or liquidity/freeze, duplicate order protection, and daily risk limit.
- Legacy V17 AI quality, V15 entry, `analysis_quality`, alignment, and participation gates are classified as `SOFT_DIAGNOSTIC_PENALTY` when AI authority is valid (`decision=TRADE`, BUY/SELL bias, schema/freshness valid, score edge present, and no hard safety block).
- The decision writer now publishes an executor authority contract in every payload: `ai_decision_authority`, `executor_authority_chain`, `executor_hard_block_scope`, and `legacy_executor_veto_policy`.
- For executable AI-authorized trades, raw legacy quality remains available as `analysis_quality_diagnostic` / `v17_quality_score_diagnostic`, while `analysis_quality` receives a V17 compatibility floor of `60` to prevent historical executor code from treating missing/zero quality as a terminal veto.
- `V17_AI_QUALITY_BLOCK` is no longer execution authority in the runtime payload contract. It is diagnostic telemetry only; the executor must proceed to broker safety checks and `OrderSend` when `decision=TRADE`, `allowed=true`, `entry_allowed=true`, and `payload_valid=true`.
- Runtime logs now emit `EXECUTOR AUTHORITY AUDIT` for executable trades, proving the AI emitted TRADE, the executor is expected to receive TRADE, legacy V15/V17 veto override is disallowed, and `OrderSend` is required after broker safety checks.

## V26.6.5A executor authority enforcement hotfix
- Runtime authority advances to `V26.6.5A | executor-authority-enforcement-hotfix`. The only valid execution chain is `AI Decision -> Payload Validation -> Broker Safety -> OrderSend -> Market`.
- When `decision=TRADE`, `allowed=true`, `payload_valid=true`, and `schema_valid=true`, legacy V15/V16/V17 strategy logic is diagnostic only and may not skip `OrderSend`. This includes `V16 ENTRY BLOCK low momentum`, `V17 AI QUALITY BLOCK`, `V17 HARD BLOCK`, and M15/M3 alignment diagnostics.
- Executor terminal blocks are restricted to invalid payload, invalid schema, stale decision, broker freeze, abnormal spread, duplicate order, insufficient margin, market closed, and catastrophic risk state.
- Executable trade payloads now publish mandatory executor log expectations: `EXECUTOR_FINAL_GATE_PASS`, `ORDER_SEND_ATTEMPT`, `ORDER_SEND_OK`, `ORDER_SEND_FAIL`, and `EXECUTOR_BUG_NO_ORDERSEND_AFTER_TRADE` if a validated TRADE reaches the executor but `OrderSend` is never called.

## V26.6.2 / V26.6.2A profit/loss asymmetry adaptive expectancy fix
- Runtime authority advances to `V26.6.2A | no-pause-adaptive-expectancy-fix`.
- Expectancy repair now treats distribution shape as the emergency: weak gap participation is disabled, loss size is compressed, and open profit is protected before trades can return to full loss.
- For reference size `0.01` lot XAUUSD, the decision payload publishes a hard realized-loss cap of `-$1.20`, a floating force-exit threshold as loss approaches the cap, and compresses new SL distance to the cap before final validation.
- Profit protection metadata is mandatory on TRADE payloads:
  - at `+$0.80` per `0.01` lot, move SL to breakeven plus spread;
  - at `+$1.20` per `0.01` lot, lock at least `+$0.50`.
- Signal expansion is explicitly not introduced. The fix reuses existing score, BB, RSI, MACD, trade-memory, and risk-payload fields only.
- Weak gap trades are disabled: `score_gap < 3` becomes `NO_TRADE`.
- `TRANSITION + NORMAL` now requires `score_gap >= 4`.
- Entries near BB middle are blocked unless RSI and MACD strongly confirm the intended direction.
- Trend-walk runner preservation remains authoritative: `MODE=TREND` with `WALK_UP` / `WALK_DOWN` continues to prefer `HOLD_TRAIL` / `TREND_RUNNER` unless existing explicit exhaustion or invalidation metadata appears.
- V26.6.2A supersedes pause behavior: loss clustering no longer creates a mandatory 30-minute pause; it publishes diagnostic telemetry, forces thesis revalidation, and applies adaptive size-down.
- V26.6.2A replaces the `<= -$5.00` daily kill switch with `DRAWDOWN_CAUTION_MODE`; new TRADE payloads may continue only as reduced-size Leg A with higher entry-location quality, while full stop is reserved for catastrophic hard-risk state.
- Measurement targets for this repair are: `Average Win >= +$1.20`, `Average Loss <= -$1.00`, and `Profit Factor > 1.30`.

## V26.6.3 exit / risk asymmetry emergency fix
- Runtime authority advances to `V26.6.3 | exit-risk-asymmetry-emergency-fix` while keeping the current entry engine intact.
- The emergency fix targets distribution shape only: hard loss cap, early damage cut, profit-lock ladder, runner damage control, runner momentum timeout, daily emergency risk stop, and loss-cluster caution.
- For reference `0.01` lot XAUUSD, published trade management now enforces maximum realized loss `-$1.20`, floating force-exit near `-$1.10`, and early damage cut at `-$0.80` if price has not first reached `+$0.60` MFE.
- Profit protection now moves to breakeven or maximum residual `-$0.10` at `+$0.60`, then locks at least `+$0.40` at `+$1.00`.
- Runner/RP_SLOT_2 inherits the same hard loss cap and must prove momentum expansion within `30-45` seconds or convert to protected exit mode / disable runner behavior.
- Daily risk is catastrophic protection only: if net daily loss is `<= -$5.00`, new entries are disabled for the session while open-position management remains active.
- Three consecutive losses activate extreme caution mode: Leg A only, reduced size, no runner, no continuation add, and tighter `-$1.00` reference loss cap.

## V26.6.4 exit authority / leg-aware profit protection fix
- Runtime authority advances to `V26.6.4 | exit-authority-leg-aware-profit-protection-fix`; entry timing and classifier structure remain unchanged.
- Exit ownership is now a single-authority contract with priority: `EMERGENCY_EXIT -> HARD_LOSS_CAP -> DAILY_GUARD_RISK_COMPRESSION -> FORCE_SCALP_TP -> LEG_A_SCALP_EXIT -> LEG_B_CONFIRMATION_EXIT -> LEG_C_RUNNER_EXIT`.
- Forced scalp mode is authority-locked: when V20.2 / `FORCE_SCALP_TP` is active, downstream management must report `effective_management_mode=SCALP_TP` and may not be overwritten by `TREND_RUNNER` or `HOLD_TRAIL`.
- Profit protection is leg-aware instead of applying one micro ladder to every position: Leg A banks small profit quickly, Leg B allows confirmation breathing room, and Leg C uses structure/momentum/BB-walk protection rather than a micro-profit-only ladder.
- Standard `0.01` XAUUSD hard loss ownership moves to the EA Executor contract: warning/protection at `-$0.80`, absolute emergency close at `-$1.00`, and AI cannot override this cap.
- Daily Guard is risk compression, not panic exit: new entries are disabled while active; profitable existing positions move to BE or lock at least `+$0.05`; losing positions continue under hard loss cap and compression instead of arbitrary `-$0.30` panic close.
- Runner timeout is not time-only: protected exit requires 30-45 seconds plus weak expansion evidence, or three consecutive weak momentum cycles.
- Decision payloads now publish per-position exit telemetry: `leg_type`, original/effective management mode, authority owner, max/current floating profit, profit lock level, hard loss/runner triggers, exit reason, realized profit, and realized R.

## V26.6.5 execution timing layer / short-term trend gate
- Runtime authority advances to `V26.6.5 | execution-timing-layer-short-term-trend-gate` while preserving the current entry engine, HTF bias engine, directional classifier logic, and indicator set.
- Directional bias and execution trigger are now independent concepts: bias answers `which direction`, while the Execution Timing Layer answers `when to enter`.
- A valid BUY/SELL bias can no longer publish immediate execution when short-term M1/M3 telemetry is strongly moving against that direction. Instead it publishes `WAIT_ENTRY_WINDOW` with `bias_preserved=true`.
- Trend context is phased into `TREND_EXPANSION`, `PULLBACK`, `RESUMPTION`, and `EXHAUSTION` using existing candle trend, structure trend, BB walk state, MACD histogram, RSI, pullback quality, continuation quality, and late-entry timing fields.
- Decision payloads now publish `execution_window_state`, `entry_window_score`, `short_term_countertrend`, `pullback_phase`, `trend_phase`, `execution_delay_reason`, `execution_window_open`, `entry_window_validation`, and `bias_preserved`.
- Strong short-term countertrend does not reverse HTF bias and does not suppress signal generation; it delays execution until recovery/resumption evidence appears.
- Expected measurement focus: reduced stop-loss frequency from countertrend entries, fewer late-pullback entries, improved average loss, and improved expectancy without reducing directional participation cadence.

## V26.6.6 expectancy diagnostic + exhaustion / protection patch
- Runtime authority advances to `V26.6.6 | expectancy-diagnostic-exhaustion-protection-patch` while preserving V26.6.5A executor authority and V26.6.5 execution timing authority.
- Entry frequency is intentionally not reduced globally. The patch targets negative expectancy by diagnosing real-vs-opposite performance, late exhaustion entries, green-to-red reversals, and same-direction loss chains.
- Every real TRADE signal now creates or updates a non-live shadow opposite-direction audit record. The shadow direction is never traded; it tracks simulated real/shadow profit, MFE, MAE, original-vs-opposite profit, and whether each side would have won.
- Exhaustion protection only intervenes when mature-move risk is clear. High exhaustion publishes `WAIT_ENTRY_WINDOW`; elevated exhaustion reduces size, disables runner behavior, and forces scalp-only management rather than turning the whole system into no-trade mode.
- Profit protection is strengthened around the observed small-win distribution: at `+$0.50` per `0.01` lot the executor should move SL to breakeven, and by `+$0.80` it should lock small profit when possible. Runner activation requires the primary/scalp leg to be protected first.
- After three consecutive losses in the same direction, only that direction is paused. The opposite thesis remains evaluable, and the paused direction resumes only after fresh continuation confirmation, a new structural setup, or exhaustion reset.
- Decision payload metrics now include win rate, average win, average loss, profit factor, original-vs-opposite profit, entry age after move, MFE/MAE, MFE-to-realized ratio, MAE-to-realized-loss ratio, loss-cluster direction, exhaustion score at entry, and profit-protection trigger state.
- V26.6.6 remains prohibited from adding live hedge trading, martingale, averaging losers, legacy executor veto resurrection, or broad entry-frequency reduction.

## V26.6.7 trade autopsy evidence patch
- Runtime authority advances to `V26.6.7 | trade-autopsy-evidence-patch` as a diagnostic-first layer; it does not change entry rules, signal generation, directional bias logic, executor authority, exit authority, profit-lock behavior, runner behavior, or risk thresholds.
- Every closed trade in `trade_memory.csv` is converted into a local autopsy record with trade identity, entry context, exit context, performance metrics, shadow audit fields, primary/secondary reason classification, confidence, and evidence fields used.
- Losing trades are classified into the approved diagnostic buckets: `WRONG_DIRECTION`, `LATE_ENTRY`, `EXHAUSTION_ENTRY`, `COUNTERTREND_ENTRY`, `CHOP_ENTRY`, `BB_MIDDLE_ROTATION`, `PROFIT_NOT_PROTECTED`, `EXIT_TOO_LATE`, `SL_TOO_WIDE`, `RUNNER_FAILED`, `THESIS_DECAY`, `MOMENTUM_FADED`, `EXECUTION_DELAY`, `SPREAD_OR_SLIPPAGE`, or `UNKNOWN`.
- Winning trades are classified into the approved diagnostic buckets: `CLEAN_TREND_CAPTURE`, `SCALP_CAPTURE`, `RUNNER_CAPTURE`, `PULLBACK_RESUMPTION_SUCCESS`, `PROFIT_LOCK_SUCCESS`, `FAST_EXIT_SUCCESS`, `SHADOW_AVOIDED`, or `OTHER_WIN`.
- Daily autopsy files are written under `logs/trade_autopsy/` as `trade_autopsy_YYYYMMDD.csv` and `trade_autopsy_summary_YYYYMMDD.json`; summaries rank loss buckets by total capital damage before any future strategy patch is attempted.

## V27 trade management dashboard architecture
- Runtime authority advances to `V27 | trade-management-dashboard-architecture` without changing AI direction, bias, entry, signal generation, or market classification logic.
- The system is split into Subsystem A (`AI Decision Engine`) for thinking/entry payload publication and Subsystem B (`Trade Management Dashboard`) for post-entry open-position management.
- Trade management parameters are loaded at runtime from `trade_management_dashboard.json` and optional `dashboard_profiles/<Profile>.json` files, allowing Conservative, Balanced, Aggressive, London Session, News Session, Scalp, and Trend profile switching without AI recompilation.
- Every post-entry exit decision remains routed through the Exit Authority Manager with exactly one effective owner.
- Backward compatibility is mandatory: missing or malformed dashboard files fall back to embedded V26.6-compatible defaults and publish fallback telemetry.

## V27.3.2 Profile_E Swing-Safe Short TP Test
- Runtime dashboard active profile advances to `Profile_E_SWING_SAFE_SHORT_TP` for a controlled post-entry exit-geometry experiment only.
- AI direction, bias, entry logic, score logic, indicator logic, market classification, and executor strategy authority remain frozen.
- Profile_E uses Profile_A as the baseline, widens the standard `0.01` XAUUSD SL from `$1.00` to `$1.30` (+30%), reduces fixed TP from `$1.00` to `$0.80` (-20%), and disables breakeven, trailing, runner, profit lock, time exit, partial exit, scaling, and pyramiding.
- Validation compares stable post-patch production Profile_A vs Profile_E data only, excluding TP_ONLY data, broken SL=0 data, decision-contract repair data, and pre-production profile data.
- Profile_E metrics must track trade count, win rate, average win/loss, profit factor, expectancy, SL/TP hit counts and rates, BE count (expected zero), average holding time, MFE, MAE, MFE capture ratio, and post-SL continuation direction when available.

## PR173 knowledge outcome attribution — ACTIVE

- Architecture: `PR173`; module: `learning.outcome_attribution`; component: Knowledge Outcome Attribution Engine.
- It provides offline deterministic, advisory-only descriptive attribution over immutable runtime and learning evidence. It emits non-causal observed associations, conditional outcome profiles, and sample-support confidence only; it cannot modify Runtime, Registry, promotion, activation, rollback, or broker execution.
- `learning.analytics` remains the separate authority for knowledge lineage, cross-version conflict, stability, and governance analytics. PR173 reports are atomic append-only artifacts under `learning_data/outcome_attribution/`.

## PR174 Governed Learning Policy Gate — ACTIVE
- `learning.learning_policy` validates one immutable PR173 outcome-attribution report for structural and minimum-sample entry into a future offline pattern-mining stage.
- It does not measure profitability, statistical stability, historical repeatability, or promotion eligibility, and has no runtime, registry, learning, mining, or promotion authority.

## PR176 governed Pattern Memory — ACTIVE

- Architecture: `PR176`; module: `learning.pattern_memory`; component: offline Pattern Memory Engine.
- PR176 consumes only an immutable PR175 `PatternMiningReport`. Each stored record retains the complete report, policy, attribution, replay, evidence-envelope, knowledge, mining-configuration, and outcome-contract provenance chain.
- One canonical governance identity derives both `memory_identity_digest` and the content-addressed memory UUID. A separate full-record digest protects all serialized record content. Records are append-only, replay-verifiable, advisory-only historical evidence.
- `STORED` means persisted historical evidence only; it does not mean approved, promoted, activated, or runtime-active.
- PR176 owns pattern history storage, memory identity, append-only persistence, immutable indexing, replay verification, and repository snapshot reporting.
- PR176 does not own learning, pattern approval or promotion, activation, knowledge promotion, Registry mutation, Runtime mutation, decision publication, broker safety, `OrderSend`, position management, or execution authority.
- Repository snapshots retain ordered memory UUID/digest pairs, counts, and previous-snapshot identity, providing an immutable append-only observation chain under `learning_data/pattern_memory/snapshots/`.

## PR177 governed Pattern Validation — ACTIVE

- Architecture: `PR177`; module: `learning.pattern_validation`; component: Governed Pattern Validation Engine.
- PR177 consumes only immutable PR176 `PatternMemoryReport` and `PatternMemoryRecord` artifacts. It reconstructs every record, verifies complete upstream provenance, source replay and snapshot binding, and applies a versioned, digest-bound historical-quality configuration.
- Outputs use the neutral states `INVALID`, `INSUFFICIENT_EVIDENCE`, and `STATISTICALLY_CONSISTENT`. Statistical consistency is **not** pattern approval, and PR177 never authorizes runtime usage.
- Validation records retain complete PR176 provenance and use a domain-separated validation UUID namespace. Reports identify the exact source artifact and distinguish newly appended validation history from duplicate replay.
- The repository is atomic and append-only and maintains domain-separated, digest-protected snapshot chains. All records, reports, snapshots, policy/config identities, and source bindings are immutable and advisory-only.
- PR177 owns historical validation, validation identity, replay verification, validation history, and repository reporting. It does not own learning, approval, promotion, activation, runtime mutation, Registry mutation, decision publication, broker safety, `OrderSend`, position management, or execution.

## PR178 governed promotion policy assessment — ACTIVE

- Architecture: `PR178`; module: `learning.pattern_promotion`; component: governed, offline Promotion Policy Assessment Engine.
- Official lineage is `PR176 Pattern Memory -> PR177 Pattern Validation -> PR178 Promotion Policy Assessment -> future separately governed Registry Admission stage`.
- PR178 owns promotion-policy identity, promotion-criteria assessment, promotion-assessment identity, replay verification, append-only assessment history, promotion-repository snapshots, and advisory-only assessment reporting.
- PR178 does **not** own Knowledge Registry publication or mutation, pattern approval, registration or activation, Runtime activation or mutation, decision publication, trading bias or direction, broker safety, `OrderSend`, position management, exit authority, or execution authority.
- `POLICY_CRITERIA_MET` means only that the immutable PR178 governance-policy criteria were satisfied. It does not mean that a pattern has been promoted, published, registered, activated, approved for Runtime use, or made tradable.
- Canonical PR178 defaults (`60` samples, `0.60` support, `0.55` confidence, and `0.05` expectancy) are independent governance selectivity thresholds, not trading-performance guarantees.

## PR179 advisory Knowledge Registry admission — ACTIVE

PR179 follows PR178 as an offline, immutable governance-recording boundary. It owns registry admission-policy identity, advisory registry-record identity, complete PR178 provenance retention, replay verification, append-only registry history, repository snapshots and integrity, and advisory-only reporting.

`ADVISORY_ENTRY_RECORDED` means only that a governance record was added to the offline Knowledge Registry. It does not make a pattern active, approved for inference, approved for Runtime consumption, tradable, or execution-authorized. PR179 has no Runtime knowledge activation or consumption, inference, pattern activation, execution approval, trading bias or direction, decision publication, broker safety, `OrderSend`, position-management, exit, or execution authority.

## PR180 Governed Advisory Runtime Knowledge Packaging Gate — ACTIVE

- Architecture: `PR180`; module: `learning.runtime_knowledge`; component: Governed Advisory Runtime Knowledge Packaging Gate.
- Official lineage is `PR176 Pattern Memory -> PR177 Pattern Validation -> PR178 Promotion Policy Assessment -> PR179 Advisory Knowledge Registry Admission -> PR180 Advisory Runtime Knowledge Packaging -> future PR181 Governed Knowledge Selector`.
- PR180 owns canonical PR179 artifact verification, immutable packaging-policy and package identity, complete PR179 provenance retention, exact snapshot membership and source binding, replay verification, append-only package history, repository snapshots and integrity, and advisory-only packaging reports.
- PR180 does not own knowledge use in Runtime decisions, selection, ranking, weighting, activation, inference, confidence, bias, scoring, direction, risk construction, decision publication, broker safety, `OrderSend`, position management, exit authority, or execution authority.
- `ADVISORY_PACKAGE_PREPARED` means only that a canonical immutable package was prepared for a future separately governed stage. It does not mean selected, active, consumed, weighted, applied, approved for inference, tradable, or execution-authorized.
