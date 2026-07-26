# PR196 Production Startup Discovery

This inventory records repository evidence gathered before completing PR196. It distinguishes tracked production behavior from deployment assumptions; PR196 does not invent an MT5 process owner.

## Authoritative findings

| Required discovery item | Repository evidence and conclusion |
|---|---|
| Production Runtime entrypoint | `bridge/ai_decision_engine_xauusd_v26_execution_confidence_engine.py::run()` is the newest tracked V26 production loop and its module-level `__main__` calls it. `start_all.bat` calls an untracked `run_ai.bat`, so the repository cannot prove the deployed command behind that batch file. |
| ExecutionContext publication | PR193 owns `ExecutionContextPublisher`, but before PR196 no production entrypoint invoked it. Its required filename is exactly `execution_context.json`. |
| Production shared-file location | The authoritative V26 Runtime uses `C:\Users\rp_fu\AppData\Roaming\MetaQuotes\Terminal\Common\Files\RP_AI_EA\shared\XAUUSD`. The MT5 V28 Executor uses the matching FILE_COMMON-relative `RP_AI_EA\\shared\\XAUUSD` directory. PR196 therefore configures the FILE_COMMON root and derives the same relative path instead of hard-coding a different Windows user. |
| Production readiness | Before PR196 no production readiness detector was wired to PR195. PR196 requires an explicit callback returning the existing `RuntimeActivationState` enum; only the exact `READY` member passes. |
| MT5 Executor startup | No tracked Python, batch, or PowerShell file launches `terminal64.exe` or attaches an EA. MT5 startup/profile ownership is external deployment state. PR196 accepts the existing host's zero-argument startup callback and invokes it only inside PR195; it does not invent a subprocess command or terminal path. |
| Legacy startup triggers | `start_all.bat` starts sync scripts and an absent `run_ai.bat`; `sync_decision_to_vps.ps1` copies a non-symbol-scoped legacy `decision.json`; V23.3 and V24 modules retain standalone historical `__main__` loops. None starts the MT5 Executor. `bridge/main.py` is an older standalone decision loop, not an Executor launcher, and is retained because deleting it would alter out-of-scope strategy code. |
| Direct Executor construction/start | Production code contains no `runtime.executor.Executor(...)` construction and no tracked MT5 start call. Constructor calls occur only in Executor tests. PR196 exposes no public direct-start method and passes the host callback only to `GovernedExecutorActivator`. |
| Startup configuration | The only tracked orchestration file is `start_all.bat`; its referenced `sync_market.ps1`, `sync_decision.ps1`, and `run_ai.bat` are absent. No tracked INI/service/task configuration controls MT5 startup. PR196 configuration is consequently explicit and fail-closed rather than inferred. |
| Windows/VPS paths | Tracked paths vary between `D:\RP_AI_EA`, users `trader`, `rp_fu`, and `rpfunds`. The live Runtime and MQL agree only on the FILE_COMMON-relative `RP_AI_EA\\shared\\XAUUSD` suffix. `RP_MT5_COMMON_FILES` and optional `RP_MT5_SYMBOL` are the authoritative PR196 settings. `pathlib.Path` joins the configured root without guessing a Windows account. |

## Wiring conclusion

The repository supports wiring the real shared-file boundary and the approved PR194/PR195 lifecycle. It does **not** support claiming that PR196 owns terminal process launch, EA installation, or chart attachment. The production host must supply its existing Executor startup callback. That callback has exactly one invocation point: PR195 after PR194 accepts the newly published file and Runtime reports `READY`.
