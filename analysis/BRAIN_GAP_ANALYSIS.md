# RP AI Brain gap analysis

## Basis and scope

This assessment compares the requested nine-stage Brain pipeline with tracked
repository evidence only. All required `brain/` documents are absent, including
the constitution, pipeline definition, and data contract. Severity therefore
includes documentation/authority risk as well as code risk. No runtime files
were modified.

| Severity | Finding | Evidence and impact |
| --- | --- | --- |
| **CRITICAL** | The mandatory Brain architecture source is absent. | There is no `brain/` directory in the tracked tree. The requested contract and authority documents cannot be pre-read or used to prove field compatibility. No implementation should begin until those source documents are restored/provided and approved under the existing V28 gate. |
| **CRITICAL** | The actual market-data producer and canonical market-state schema are outside the repository. | The authoritative Python engine only reads the Common Files `market_state.json`; tracked MQL reads it but does not write it. A new perception layer cannot be safely specified, validated, or replayed without the producer, ownership, example payloads, and schema/version contract. |
| **HIGH** | Current intelligence is tightly coupled into one monolithic runtime module. | `bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py` combines input transport, perception, classification, thesis selection, filters, confidence, risk construction, learning, compatibility, dashboard import, validation, and publication. Stage isolation and testability are weak. |
| **HIGH** | Indicator-score logic is performing market-understanding work. | `build_decision()` uses `buy_score`/`sell_score` with RSI/MACD/MA/BB to derive BB state and `classify_market()` derives `market_mode` partly from the same score dominance. This mixes observed structure with score-based directional preference and can make a score look like a regime fact. |
| **HIGH** | Expected value is incomplete at decision time. | The engine enforces planned RR and rule-based expectancy/loss filters; `analysis/trade_statistics.py` and `analysis/trade_autopsy_engine.py` calculate realized outcomes offline. There is no explicit decision-time expected-value input composed from calibrated probability, payoff distribution, costs/spread, and alternative actions. |
| **HIGH** | Probability/confidence is heuristic rather than an explicit probability engine. | Execution confidence, analysis quality, entry-location score, and entry-window score are multiple heuristic scales. No calibration dataset, probability semantics, reliability measurement, or forecast contract is evident. |
| **HIGH** | Architecture authority is internally inconsistent around V28. | The authority documents say V28 is proposal-only and no implementation is authorized pending approval. Yet tracked V28 clean-core/executor code and V29 extensions exist, and V26 contains functions named `enforce_final_execution_state_v28`. They must remain non-authoritative unless the governance documents are updated/approved. |
| HIGH | The publication boundary has substantial alias/compatibility coupling. | `ensure_ea_v17_compat_fields()` and publication code preserve overlapping action, mode, stop/target, management, size, and freshness names. A Brain-stage output cannot be introduced directly without an explicit adapter and parity testing against `decision.json`. |
| HIGH | Position intelligence is split across Python and MT5 and Python imports dashboard configuration. | Python constructs initial risk payload and imports `load_trade_management_dashboard`; the dashboard MQL owns post-entry management. This creates hidden coupling between entry publication, JSON profile configuration, and executor/dashboard semantics. |
| MEDIUM | Multiple existing modules duplicate decision concepts. | V26 contains execution-quality/timing/entry-location logic; V28 `clean_core.py` has score-gap direction/risk logic; V29 `decision_core.py` and `entry_quality_engine.py` score entry quality. V23 and V24 are parallel legacy engines. Their roles are not declared in a single runtime registry. |
| MEDIUM | Learning has two disconnected ownership paths. | V26 updates a local learning state from trade records, while `analysis/` computes statistics and autopsies. There is no tracked promotion contract describing which outcomes may change live behavior, validation thresholds, lineage, or rollback. |
| MEDIUM | Raw market-state field quality is not established. | Candle history and several fields are optional/fallback-driven; comments explicitly avoid blocking when candle history is absent. This is practical compatibility behavior, but it means downstream structure conclusions may be based on different evidence sets. |
| MEDIUM | The attached live executor cannot be proven from the repository. | Both the V27 dashboard and V28/V29 MQL modules consume decision data, but terminal attachment/launch configuration is not tracked. This prevents a fully authoritative end-to-end runtime topology. |
| LOW | Offline analysis is useful but not a Brain learning service. | `trade_statistics.py`, `trade_autopsy_engine.py`, and cohort analysis offer metrics/evidence but do not expose a versioned, validated feedback artifact to a decision engine. |

## What already exists

* A robust file-based market-data adapter with freshness metadata, an atomic
  decision publisher, extensive payload validation, and compatibility fields.
* Perception-like indicator/candle derivation and understanding-like market
  structure/regime functions in the V26 engine.
* Reasoning, confidence, entry location/timing, risk construction, multi-leg
  metadata, and initial exit metadata in the V26 engine.
* Separate post-entry dashboard configuration and MQL dashboard management.
* Trade-statistics and trade-autopsy analysis utilities with tests.

## Missing or incomplete Brain capabilities

* The Brain architecture documents, contract, and approved implementation
  boundary.
* A tracked authoritative market-state producer/schema and replay fixtures.
* Explicit stage input/output contracts and immutable evidence snapshots.
* A separated market-understanding model that does not treat score dominance as
  a regime fact.
* Calibrated probability and decision-time expected value.
* A controlled learning feedback/promotion/rollback contract.
* An authoritative runtime launcher/terminal deployment manifest proving which
  MQL executor is live.

## Authority violations or risks to preserve during migration

* Do not let an executor perform Python-side intelligence: MQL must retain only
  the broker/payload hard-safety responsibilities stipulated in
  `DECISION_FLOW_MAP.md`; quality, alignment, and directional logic must not
  become executor vetoes.
* Do not let the post-entry dashboard take direction, bias, entry-timing, or
  market-classification authority. Its current role is post-entry management.
* Do not treat the V28/V29 files as a licensed replacement runtime merely
  because they exist; current governance explicitly retains the V26 engine.
* Do not normalize/remove aliases or alter `decision.json` until the missing
  data contract defines an adapter and compatibility period.
