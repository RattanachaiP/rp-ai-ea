# PR240 Development Startup

## Purpose

PR240 provides a convenient Windows development launcher without creating a second
Runtime authority path. `runtime.dev_startup` delegates directly to
`runtime.production_startup`; consequently development startup retains the exact
owner-governed PR184 activation and PR185 through PR190 construction, persistence,
lineage, immutable package consumption, and fail-closed Runtime handoff.

The development entrypoint does not import or launch the V26 Decision Engine itself.
It does not select a latest record, manufacture observations, repair an artifact, or
change `PACKAGE_MISSING` behavior. The AI Decision Engine,
ExecutionConfidenceIntegration, Executor, and all trading and execution authority
remain unchanged.

## Windows launch

From PowerShell, run:

```powershell
.\start_ai_runtime.ps1
```

The script derives the repository root from its own location, verifies that `python`
is on `PATH`, changes to the repository root, and asks the same governed canonical
path resolver used by production startup for the `market_state.json` location. It
stops before startup if that file is absent. Set `RP_AI_SHARED_ROOT` when the feed is
outside the canonical MT5 Common Files location; the expected file is then
`$env:RP_AI_SHARED_ROOT\XAUUSD\market_state.json`.

After preflight, the launcher executes only:

```powershell
python -m runtime.dev_startup
```

All subsequent validation and startup is owned by `runtime.production_startup`.
Missing or corrupt PR184 activation, telemetry, PR185–PR190 artifacts, or package
lineage remains a terminal fail-closed condition.
