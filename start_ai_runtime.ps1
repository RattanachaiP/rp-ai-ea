[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# This file lives at the repository root. Resolve it rather than relying on the
# operator's current directory so module imports and learning_data roots are stable.
$RepositoryRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path -LiteralPath (Join-Path $RepositoryRoot "runtime\production_startup.py") -PathType Leaf)) {
    throw "Unable to detect the RP AI EA repository root from launcher path: $RepositoryRoot"
}

$Python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $Python) {
    throw "Python was not found on PATH. Install Python or add python.exe to PATH."
}

Push-Location $RepositoryRoot
try {
    # Ask the governed resolver for the exact path that production startup will read.
    $MarketStatePath = & $Python.Source -c "from runtime.environment_observation import canonical_market_state_path; print(canonical_market_state_path())"
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($MarketStatePath)) {
        throw "Unable to resolve the canonical market_state.json path."
    }
    $MarketStatePath = $MarketStatePath.Trim()
    if (-not (Test-Path -LiteralPath $MarketStatePath -PathType Leaf)) {
        throw "Required market_state.json does not exist: $MarketStatePath"
    }

    python -m runtime.dev_startup
    if ($LASTEXITCODE -ne 0) {
        throw "Governed AI Runtime startup failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
