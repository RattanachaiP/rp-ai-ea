[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$MarketState = "",
    [double]$ObservationWindow = 5.0
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

Write-Host "RP AI EA — Canonical Runtime Startup" -ForegroundColor Cyan
Write-Host "Repository: $repoRoot"

try {
    & $Python --version
    if ($LASTEXITCODE -ne 0) {
        throw "PYTHON_NOT_AVAILABLE"
    }
} catch {
    throw "Python could not be started. Install/configure Python or pass -Python with the executable path. Detail: $($_.Exception.Message)"
}

$arguments = @(
    "-m",
    "runtime.production_startup",
    "--observation-window",
    $ObservationWindow.ToString([System.Globalization.CultureInfo]::InvariantCulture)
)

if (-not [string]::IsNullOrWhiteSpace($MarketState)) {
    $resolvedMarketState = (Resolve-Path -LiteralPath $MarketState).Path
    $arguments += @("--market-state", $resolvedMarketState)
}

Write-Host "Starting canonical governed pipeline:" -ForegroundColor Green
Write-Host "PR184 activation -> PR185 -> PR186 -> PR187 -> PR188 -> PR189 -> PR190 -> Python Runtime"
Write-Host "Do not launch bridge\ai_decision_engine_xauusd_v26_execution_confidence_engine.py directly."

& $Python @arguments
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Error "Canonical Runtime startup failed with exit code $exitCode. Read the final governed failure reason; do not set RP_EXECUTION_PACKAGE_UUID manually."
    exit $exitCode
}
