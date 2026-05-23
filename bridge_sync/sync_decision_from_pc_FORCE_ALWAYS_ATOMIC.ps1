# sync_decision_from_pc_FORCE_ALWAYS_ATOMIC.ps1
# RP AI+EA Decision Sync: PC -> VPS
# Version: FORCE ALWAYS ATOMIC
# No hash gating. Always sync every loop.

$source = "\\tsclient\D\RP_AI_EA\shared\XAUUSD\decision.json"
$target = "C:\Users\trader\AppData\Roaming\MetaQuotes\Terminal\Common\Files\RP_AI_EA\shared\XAUUSD\decision.json"

$intervalMs = 500
$maxRetries = 10
$retrySleepMs = 100
$staleWarnSeconds = 10

$script:lastTargetSignal = ""
$script:lastTargetSignalChange = Get-Date

function Get-JsonField {
    param([string]$Path, [string]$Field)
    try {
        if (!(Test-Path $Path)) { return "" }
        $raw = Get-Content -Path $Path -Raw -Encoding UTF8 -ErrorAction Stop
        if ([string]::IsNullOrWhiteSpace($raw)) { return "" }
        $json = $raw | ConvertFrom-Json -ErrorAction Stop
        $value = $json.$Field
        if ($null -eq $value) { return "" }
        return [string]$value
    } catch { return "" }
}

function Get-FileTimeText {
    param([string]$Path)
    try {
        if (!(Test-Path $Path)) { return "MISSING" }
        return (Get-Item $Path -ErrorAction Stop).LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss.fff")
    } catch { return "ERR" }
}

function Get-FileLength {
    param([string]$Path)
    try {
        if (!(Test-Path $Path)) { return -1 }
        return (Get-Item $Path -ErrorAction Stop).Length
    } catch { return -1 }
}

function Remove-WithRetry {
    param([string]$Path)
    if (!(Test-Path $Path)) { return $true }

    for ($i = 1; $i -le $maxRetries; $i++) {
        try {
            Remove-Item -Path $Path -Force -ErrorAction Stop
            return $true
        } catch {
            Write-Host "$(Get-Date -Format HH:mm:ss.fff) delete retry $i/$maxRetries | $($_.Exception.Message)"
            Start-Sleep -Milliseconds $retrySleepMs
        }
    }
    return $false
}

function Rename-WithRetry {
    param([string]$TempPath, [string]$TargetPath)
    $targetName = Split-Path $TargetPath -Leaf

    for ($i = 1; $i -le $maxRetries; $i++) {
        try {
            Rename-Item -Path $TempPath -NewName $targetName -ErrorAction Stop
            return $true
        } catch {
            Write-Host "$(Get-Date -Format HH:mm:ss.fff) rename retry $i/$maxRetries | $($_.Exception.Message)"
            Start-Sleep -Milliseconds $retrySleepMs
        }
    }
    return $false
}

function Sync-DecisionAlwaysAtomic {
    if (!(Test-Path $source)) {
        Write-Host "$(Get-Date -Format HH:mm:ss.fff) SOURCE MISSING | $source"
        return $false
    }

    $targetDir = Split-Path $target -Parent
    if (!(Test-Path $targetDir)) {
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    }

    $stamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
    $tempTarget = Join-Path $targetDir "decision.$stamp.$PID.tmp"

    $srcTimeBefore = Get-FileTimeText $source
    $targetTimeBefore = Get-FileTimeText $target
    $srcSignal = Get-JsonField -Path $source -Field "updated_at"
    if ([string]::IsNullOrWhiteSpace($srcSignal)) {
        $srcSignal = Get-JsonField -Path $source -Field "signal_time"
    }

    try {
        Copy-Item -Path $source -Destination $tempTarget -Force -ErrorAction Stop

        if (!(Test-Path $tempTarget)) {
            Write-Host "$(Get-Date -Format HH:mm:ss.fff) COPY FAIL | temp missing"
            return $false
        }

        $tmpLen = Get-FileLength $tempTarget
        if ($tmpLen -le 20) {
            Write-Host "$(Get-Date -Format HH:mm:ss.fff) COPY FAIL | temp too small len=$tmpLen | target preserved"
            Remove-Item -Path $tempTarget -Force -ErrorAction SilentlyContinue
            return $false
        }

        if (!(Remove-WithRetry -Path $target)) {
            Write-Host "$(Get-Date -Format HH:mm:ss.fff) REPLACE SKIP | target locked, old decision preserved"
            Remove-Item -Path $tempTarget -Force -ErrorAction SilentlyContinue
            return $false
        }

        if (!(Rename-WithRetry -TempPath $tempTarget -TargetPath $target)) {
            Write-Host "$(Get-Date -Format HH:mm:ss.fff) RENAME FAIL | attempting safe copy fallback"
            try {
                Copy-Item -Path $tempTarget -Destination $target -Force -ErrorAction Stop
                Remove-Item -Path $tempTarget -Force -ErrorAction SilentlyContinue
            } catch {
                Write-Host "$(Get-Date -Format HH:mm:ss.fff) FALLBACK FAIL | $($_.Exception.Message)"
                return $false
            }
        }

        $targetTimeAfter = Get-FileTimeText $target
        $targetLen = Get-FileLength $target
        $targetSignal = Get-JsonField -Path $target -Field "updated_at"
        if ([string]::IsNullOrWhiteSpace($targetSignal)) {
            $targetSignal = Get-JsonField -Path $target -Field "signal_time"
        }

        $now = Get-Date
        if ($targetSignal -ne $script:lastTargetSignal) {
            $script:lastTargetSignal = $targetSignal
            $script:lastTargetSignalChange = $now
        } else {
            $age = ($now - $script:lastTargetSignalChange).TotalSeconds
            if ($age -gt $staleWarnSeconds) {
                Write-Host "$(Get-Date -Format HH:mm:ss.fff) STALE WARNING | target signal unchanged > $staleWarnSeconds sec | signal=$targetSignal | srcTime=$srcTimeBefore | targetTime=$targetTimeAfter"
            }
        }

        Write-Host "$(Get-Date -Format HH:mm:ss.fff) FORCE SYNC OK | sourceTime=$srcTimeBefore | oldTarget=$targetTimeBefore | newTarget=$targetTimeAfter | srcSignal=$srcSignal | targetSignal=$targetSignal | len=$targetLen"
        return $true
    } catch {
        Write-Host "$(Get-Date -Format HH:mm:ss.fff) SYNC ERROR | $($_.Exception.Message)"
        if (Test-Path $tempTarget) {
            Remove-Item -Path $tempTarget -Force -ErrorAction SilentlyContinue
        }
        return $false
    }
}

Write-Host "============================================================"
Write-Host "RP Decision Sync FORCE ALWAYS ATOMIC started"
Write-Host "IMPORTANT: Kill old sync scripts before running this one."
Write-Host "Source: $source"
Write-Host "Target: $target"
Write-Host "IntervalMs: $intervalMs | Retries: $maxRetries | RetrySleepMs: $retrySleepMs"
Write-Host "NO HASH GATING: sync runs every loop."
Write-Host "============================================================"

while ($true) {
    Sync-DecisionAlwaysAtomic | Out-Null
    Start-Sleep -Milliseconds $intervalMs
}
