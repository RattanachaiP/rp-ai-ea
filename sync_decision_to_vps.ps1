<#
RP AI+EA Decision Sync: PC -> VPS
Version: V26.6.1 decision pipeline integrity fix

Fixes the legacy path mismatch that copied:
  D:\RP_AI_EA\shared\decision.json
instead of the symbol-scoped AI output:
  D:\RP_AI_EA\shared\XAUUSD\decision.json

The sync is atomic and noisy by design: no silent exceptions, source/target
freshness telemetry every copy, stale warnings when decision fields stop moving,
and sequence-aware skip telemetry when the PC-side decision has not changed.
#>

param(
    [string]$Source = "D:\RP_AI_EA\shared\XAUUSD\decision.json",
    [string]$Target = "C:\Users\trader\AppData\Roaming\MetaQuotes\Terminal\Common\Files\RP_AI_EA\shared\XAUUSD\decision.json",
    [int]$IntervalMs = 500,
    [int]$MaxRetries = 10,
    [int]$RetrySleepMs = 100,
    [int]$HeartbeatEvery = 20,
    [int]$StaleWarnSeconds = 10
)

$script:lastSeenChangeKey = ""
$script:lastTargetSignal = ""
$script:lastTargetSignalChange = Get-Date
$script:skip_count = 0
$script:lock_retry_count = 0
$script:loop_count = 0

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
    } catch {
        Write-Host "$(Get-Date -Format HH:mm:ss.fff) JSON READ ERROR | path=$Path | field=$Field | $($_.Exception.Message)"
        return ""
    }
}

function Get-FileTimeText {
    param([string]$Path)
    try {
        if (!(Test-Path $Path)) { return "MISSING" }
        return (Get-Item $Path -ErrorAction Stop).LastWriteTimeUtc.ToString("yyyy-MM-dd HH:mm:ss.fff") + "Z"
    } catch { return "ERR" }
}

function Get-FileLength {
    param([string]$Path)
    try {
        if (!(Test-Path $Path)) { return -1 }
        return (Get-Item $Path -ErrorAction Stop).Length
    } catch { return -1 }
}

function Move-AtomicallyWithRetry {
    param([string]$TempPath, [string]$TargetPath)
    for ($i = 1; $i -le $MaxRetries; $i++) {
        try {
            Move-Item -Path $TempPath -Destination $TargetPath -Force -ErrorAction Stop
            return $true
        } catch {
            $script:lock_retry_count++
            Write-Host "$(Get-Date -Format HH:mm:ss.fff) MOVE RETRY $i/$MaxRetries | $($_.Exception.Message)"
            Start-Sleep -Milliseconds ($RetrySleepMs * [math]::Min($i, 10))
        }
    }
    return $false
}

function Get-DecisionChangeKey {
    param([string]$Path)
    $decisionSeq = Get-JsonField -Path $Path -Field "decision_sequence_id"
    if (![string]::IsNullOrWhiteSpace($decisionSeq)) { return "DSEQ:$decisionSeq" }

    $seq = Get-JsonField -Path $Path -Field "sequence_id"
    if (![string]::IsNullOrWhiteSpace($seq)) { return "SEQ:$seq" }

    try { return "UTC:$((Get-Item $Path -ErrorAction Stop).LastWriteTimeUtc.Ticks)" }
    catch { return "UTC:MISSING" }
}

function Sync-DecisionAtomic {
    $script:loop_count++
    if (!(Test-Path $Source)) {
        Write-Host "$(Get-Date -Format HH:mm:ss.fff) SOURCE MISSING | source=$Source | target=$Target"
        return $false
    }

    $targetDir = Split-Path $Target -Parent
    if (!(Test-Path $targetDir)) {
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    }

    $srcChangeKey = Get-DecisionChangeKey -Path $Source
    $srcUpdatedAt = Get-JsonField -Path $Source -Field "updated_at"
    $srcDecisionHeartbeat = Get-JsonField -Path $Source -Field "decision_heartbeat_unix"
    $srcDecisionSeq = Get-JsonField -Path $Source -Field "decision_sequence_id"
    $srcSignal = Get-JsonField -Path $Source -Field "signal"
    if ([string]::IsNullOrWhiteSpace($srcSignal)) { $srcSignal = Get-JsonField -Path $Source -Field "signal_time" }

    if ($srcChangeKey -eq $script:lastSeenChangeKey) {
        $script:skip_count++
        if (($script:skip_count % $HeartbeatEvery) -eq 0) {
            Write-Host "$(Get-Date -Format HH:mm:ss.fff) HEARTBEAT | skip_count=$($script:skip_count) | lock_retry_count=$($script:lock_retry_count) | source=$Source | target=$Target | change_key=$srcChangeKey | updated_at=$srcUpdatedAt | decision_heartbeat_unix=$srcDecisionHeartbeat"
        }
        return $true
    }

    $stamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
    $tempTarget = Join-Path $targetDir "decision.$stamp.$PID.tmp"
    $srcTimeBefore = Get-FileTimeText $Source
    $targetTimeBefore = Get-FileTimeText $Target

    try {
        Copy-Item -Path $Source -Destination $tempTarget -Force -ErrorAction Stop
        $tmpLen = Get-FileLength $tempTarget
        if ($tmpLen -le 20) {
            Write-Host "$(Get-Date -Format HH:mm:ss.fff) COPY FAIL | temp too small len=$tmpLen | source=$Source | target preserved=$Target"
            Remove-Item -Path $tempTarget -Force -ErrorAction SilentlyContinue
            return $false
        }

        if (!(Move-AtomicallyWithRetry -TempPath $tempTarget -TargetPath $Target)) {
            Write-Host "$(Get-Date -Format HH:mm:ss.fff) REPLACE FAIL | target locked | source=$Source | target=$Target"
            Remove-Item -Path $tempTarget -Force -ErrorAction SilentlyContinue
            return $false
        }

        $targetTimeAfter = Get-FileTimeText $Target
        $targetLen = Get-FileLength $Target
        $targetUpdatedAt = Get-JsonField -Path $Target -Field "updated_at"
        $targetDecisionHeartbeat = Get-JsonField -Path $Target -Field "decision_heartbeat_unix"
        $targetDecisionSeq = Get-JsonField -Path $Target -Field "decision_sequence_id"

        $now = Get-Date
        $targetFreshnessKey = "$targetDecisionSeq|$targetDecisionHeartbeat|$targetUpdatedAt"
        if ($targetFreshnessKey -ne $script:lastTargetSignal) {
            $script:lastTargetSignal = $targetFreshnessKey
            $script:lastTargetSignalChange = $now
        } else {
            $age = ($now - $script:lastTargetSignalChange).TotalSeconds
            if ($age -gt $StaleWarnSeconds) {
                Write-Host "$(Get-Date -Format HH:mm:ss.fff) STALE WARNING | target unchanged > $StaleWarnSeconds sec | source=$Source | target=$Target | target_key=$targetFreshnessKey"
            }
        }

        $script:lastSeenChangeKey = $srcChangeKey
        $script:skip_count = 0
        Write-Host "$(Get-Date -Format HH:mm:ss.fff) DECISION SYNC OK | source=$Source | target=$Target | oldTarget=$targetTimeBefore | sourceTime=$srcTimeBefore | newTarget=$targetTimeAfter | src_decision_sequence_id=$srcDecisionSeq | target_decision_sequence_id=$targetDecisionSeq | src_decision_heartbeat_unix=$srcDecisionHeartbeat | target_decision_heartbeat_unix=$targetDecisionHeartbeat | src_updated_at=$srcUpdatedAt | target_updated_at=$targetUpdatedAt | src_signal=$srcSignal | len=$targetLen"
        return $true
    } catch {
        Write-Host "$(Get-Date -Format HH:mm:ss.fff) SYNC ERROR | source=$Source | target=$Target | $($_.Exception.Message)"
        if (Test-Path $tempTarget) { Remove-Item -Path $tempTarget -Force -ErrorAction SilentlyContinue }
        return $false
    }
}

Write-Host "============================================================"
Write-Host "RP Decision Sync V26.6.1 atomic path-integrity mode started"
Write-Host "Source: $Source"
Write-Host "Target: $Target"
Write-Host "IntervalMs: $IntervalMs | Retries: $MaxRetries | RetrySleepMs: $RetrySleepMs"
Write-Host "Required source fields: heartbeat_unix, decision_heartbeat_unix, sequence_id, decision_sequence_id, signal, updated_at"
Write-Host "============================================================"

while ($true) {
    Sync-DecisionAtomic | Out-Null
    Start-Sleep -Milliseconds $IntervalMs
}
