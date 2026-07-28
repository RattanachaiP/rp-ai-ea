[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# This file lives at the repository root. Resolve it rather than relying on the
# operator's current directory so module imports and learning_data roots are stable.
$RepositoryRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path -LiteralPath (Join-Path $RepositoryRoot "bridge\ai_decision_engine_xauusd_v26_execution_confidence_engine.py") -PathType Leaf)) {
    throw "Unable to detect the RP AI EA repository root from launcher path: $RepositoryRoot"
}

$Python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $Python) {
    throw "Python was not found on PATH. Install Python or add python.exe to PATH."
}

Push-Location $RepositoryRoot
try {
    # Resolve the exact path used by the established Demo decision engine.
    $MarketStatePath = & $Python.Source -c "from bridge.ai_decision_engine_xauusd_v26_execution_confidence_engine import FILE_PATH; print(FILE_PATH)"
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($MarketStatePath)) {
        throw "Unable to resolve the canonical market_state.json path."
    }
    $MarketStatePath = $MarketStatePath.Trim()
    if (-not (Test-Path -LiteralPath $MarketStatePath -PathType Leaf)) {
        throw "Required market_state.json does not exist: $MarketStatePath"
    }

    & $Python.Source -m bridge.ai_decision_engine_xauusd_v26_execution_confidence_engine
    if ($LASTEXITCODE -ne 0) {
        throw "AI Demo Runtime startup failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
