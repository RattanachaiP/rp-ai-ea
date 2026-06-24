# V28 Clean Core Rebuild

## V28 files created

- `bridge/v28/clean_core.py` — minimal Python AI decision path.
- `bridge/v28/payload_contract.py` — shared Python/executor payload contract validator.
- `bridge/v28/dashboard_contract.py` — dashboard-owned exit-management contract loader.
- `mt5/v28/RP_AI_Executor_V28_CleanCore.mq5` — strategy-free executor contract path.
- `trade_management_dashboard_v28.json` — runtime dashboard contract configuration.
- `tests/test_v28_clean_core.py` — contract and decision tests.

## V27 components intentionally not ported

Soft Lock, Transition Wait, Weak Gap hard NO_TRADE, Entry Location hard block, Low Confidence hard veto, V17 AI Quality Block, V16 Momentum hard block, V15 M15/M3 hard alignment block, Cooldown Max Signal Block, legacy final gates, old SL/BE/TP managers, hidden PositionClose logic, hidden PositionModify logic, duplicated protection authority, duplicated execution timing gates, and duplicated final schema normalization gates are not imported into V28.

## Clean decision flow

`Market State Writer -> Python AI V28 clean_core.decide -> Dashboard Contract -> Payload Contract -> Executor Broker Safety -> OrderSend`

Only these V28 blocks may publish `NO_TRADE`: missing BUY/SELL direction, `score_gap` below configurable minimum, stale market data, dashboard trade disabled, open-position limit, or invalid risk package.

## Clean payload schema

Executable `TRADE` payloads use `V28_EXECUTABLE_PAYLOAD_1` and require: `decision`, `direction`, `bias`, `entry_price`, `lot`, `dashboard_profile`, `management_mode`, `broker_sl_required`, `broker_tp_required`, `stop_loss` or approved SL suppression, `take_profit` or approved dashboard TP contract, `payload_valid=true`, `sequence_id`, and `heartbeat_unix`.

Every cycle publishes `decision`, `reason`, `score_gap`, `score_min_required`, `final_authority`, `payload_valid`, `trade_block_reason`, `dashboard_profile`, and `executor_contract_status`.

## Executor contract

The V28 executor validates only schema/contract and broker safety before `OrderSend`. It does not reinterpret strategy and does not contain V15/V16/V17 quality, alignment, cooldown, location, soft-lock, transition, or legacy final strategy gates.

Required executor logs are `EXECUTOR_CONTRACT_PASS`, `ORDER_SEND_ATTEMPT`, and exactly one of `ORDER_SEND_OK` or `ORDER_SEND_FAIL` for accepted trade payloads.

## Dashboard contract

The dashboard owns fixed TP, broker SL on/off, BE, trailing, profit lock, runner, emergency entry/close toggles, time exit, and partial close settings. Python publishes the loaded dashboard contract; executor logs the selected profile and management mode.

## Known limitations

- V28 is parallel and does not delete or replace V27 launch scripts.
- MQL5 compilation requires MetaEditor/MT5, which is not available in this Linux container.
- Backtest/live validation requires an MT5 terminal and broker connection; this repository validation covers Python payload behavior and static executor contract presence only.
