# sync_market_state_to_pc_FORCE_ALWAYS_ATOMIC.ps1
# RP AI+EA Market State Sync: VPS -> PC
# Version: FORCE ALWAYS ATOMIC
# No hash gating. Always sync every loop.

$source = "C:\Users\trader\AppData\Roaming\MetaQuotes\Terminal\Common\Files\RP_AI_EA\shared\XAUUSD\market_state.json"
$target = "\\tsclient\D\RP_AI_EA\shared\XAUUSD\market_state.json"

$intervalMs = 500
$maxRetries = 10
$retrySleepMs = 100
$HeartbeatEvery = 20
$staleWarnSeconds = 5

$script:lastTargetServerTime = ""
$script:lastTargetServerTimeChange = Get-Date
$script:lastSeenSequence = ""
$script:lastSeenWriteUtc = [datetime]::MinValue
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
    } catch { return "" }
}

function Get-FileTimeText {
    param([string]$Path)
    try {
        if (!(Test-Path $Path)) { return "MISSING" }
        return (Get-Item $Path -ErrorAction Stop).LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss.fff")
    } catch { return "ERR" }
}

function Get-FileAgeSeconds {
    param([string]$Path)
    try {
        if (!(Test-Path $Path)) { return 999999 }
        return [int]((Get-Date) - (Get-Item $Path -ErrorAction Stop).LastWriteTime).TotalSeconds
    } catch { return 999999 }
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
            $script:lock_retry_count++
            Write-Host "$(Get-Date -Format HH:mm:ss.fff) delete retry $i/$maxRetries | $($_.Exception.Message)"
            Start-Sleep -Milliseconds ($retrySleepMs * [math]::Min($i, 10))
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
            $script:lock_retry_count++
            Write-Host "$(Get-Date -Format HH:mm:ss.fff) rename retry $i/$maxRetries | $($_.Exception.Message)"
            Start-Sleep -Milliseconds ($retrySleepMs * [math]::Min($i, 10))
        }
    }
    return $false
}

function Replace-AtomicallyWithRetry {
    param([string]$TempPath, [string]$TargetPath)
    for ($i = 1; $i -le $maxRetries; $i++) {
        try {
            Move-Item -Path $TempPath -Destination $TargetPath -Force -ErrorAction Stop
            return $true
        } catch {
            $script:lock_retry_count++
            Write-Host "$(Get-Date -Format HH:mm:ss.fff) move retry $i/$maxRetries | $($_.Exception.Message)"
            Start-Sleep -Milliseconds ($retrySleepMs * [math]::Min($i, 10))
        }
    }
    return $false
}

function Sync-MarketStateAlwaysAtomic {
    $script:loop_count++
    if (!(Test-Path $source)) {
        Write-Host "$(Get-Date -Format HH:mm:ss.fff) SOURCE MISSING | $source"
        return $false
    }

    $targetDir = Split-Path $target -Parent
    if (!(Test-Path $targetDir)) {
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    }

    $stamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
    $tempTarget = Join-Path $targetDir "market_state.$stamp.$PID.tmp"

    $srcTime = Get-FileTimeText $source
    $targetTimeBefore = Get-FileTimeText $target
    $srcAge = Get-FileAgeSeconds $source
    $targetAge = Get-FileAgeSeconds $target

    $srcServerTime = Get-JsonField -Path $source -Field "server_time"
    $srcSequence   = Get-JsonField -Path $source -Field "sequence_id"
    $srcWriteUtc   = (Get-Item $source -ErrorAction Stop).LastWriteTimeUtc
    $srcBarTime    = Get-JsonField -Path $source -Field "bar_time"
    $srcBid        = Get-JsonField -Path $source -Field "bid"
    $srcBuyScore   = Get-JsonField -Path $source -Field "buyScore"
    $srcSellScore  = Get-JsonField -Path $source -Field "sellScore"
    if ([string]::IsNullOrWhiteSpace($srcBuyScore)) { $srcBuyScore = Get-JsonField -Path $source -Field "buy_score" }
    if ([string]::IsNullOrWhiteSpace($srcSellScore)) { $srcSellScore = Get-JsonField -Path $source -Field "sell_score" }

    $changeKey = if (![string]::IsNullOrWhiteSpace($srcSequence)) { "SEQ:$srcSequence" } else { "UTC:$($srcWriteUtc.Ticks)" }
    $lastKey = if (![string]::IsNullOrWhiteSpace($script:lastSeenSequence)) { "SEQ:$script:lastSeenSequence" } else { "UTC:$($script:lastSeenWriteUtc.Ticks)" }
    if ($changeKey -eq $lastKey) {
        $script:skip_count++
        if (($script:skip_count % $HeartbeatEvery) -eq 0) {
            Write-Host "$(Get-Date -Format HH:mm:ss.fff) HEARTBEAT skip=$($script:skip_count) lock_retry_count=$($script:lock_retry_count) sequence_id=$srcSequence LastWriteTimeUtc=$srcWriteUtc"
        }
        return $true
    }

    if ($srcAge -gt $staleWarnSeconds) {
        Write-Host "$(Get-Date -Format HH:mm:ss.fff) SOURCE STALE WARNING | source age=$srcAge sec | server_time=$srcServerTime | source=$source"
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

        if (!(Replace-AtomicallyWithRetry -TempPath $tempTarget -TargetPath $target)) {
            Write-Host "$(Get-Date -Format HH:mm:ss.fff) REPLACE SKIP | target locked, old market_state preserved"
            Remove-Item -Path $tempTarget -Force -ErrorAction SilentlyContinue
            return $false
        }

        $targetTimeAfter = Get-FileTimeText $target
        $targetLen = Get-FileLength $target
        $targetAgeAfter = Get-FileAgeSeconds $target
        $targetServerTime = Get-JsonField -Path $target -Field "server_time"
        $targetBid = Get-JsonField -Path $target -Field "bid"
        $targetBuyScore = Get-JsonField -Path $target -Field "buyScore"
        $targetSellScore = Get-JsonField -Path $target -Field "sellScore"
        if ([string]::IsNullOrWhiteSpace($targetBuyScore)) { $targetBuyScore = Get-JsonField -Path $target -Field "buy_score" }
        if ([string]::IsNullOrWhiteSpace($targetSellScore)) { $targetSellScore = Get-JsonField -Path $target -Field "sell_score" }

        $now = Get-Date
        if ($targetServerTime -ne $script:lastTargetServerTime) {
            $script:lastTargetServerTime = $targetServerTime
            $script:lastTargetServerTimeChange = $now
        } else {
            $unchangedAge = ($now - $script:lastTargetServerTimeChange).TotalSeconds
            if ($unchangedAge -gt $staleWarnSeconds) {
                Write-Host "$(Get-Date -Format HH:mm:ss.fff) TARGET STALE WARNING | target server_time unchanged > $staleWarnSeconds sec | server_time=$targetServerTime | targetAge=$targetAgeAfter sec"
            }
        }

        if ($targetAgeAfter -gt $staleWarnSeconds) {
            Write-Host "$(Get-Date -Format HH:mm:ss.fff) TARGET FILETIME STALE WARNING | target age=$targetAgeAfter sec | target=$target"
        }

        $script:lastSeenSequence = $srcSequence
        $script:lastSeenWriteUtc = $srcWriteUtc
        $script:skip_count = 0
        Write-Host "$(Get-Date -Format HH:mm:ss.fff) FORCE MARKET SYNC OK | srcTime=$srcTime | oldTarget=$targetTimeBefore | newTarget=$targetTimeAfter | srcAge=$srcAge sec | targetAgeBefore=$targetAge sec | server=$srcServerTime | bar=$srcBarTime | bid=$srcBid->$targetBid | score=${srcBuyScore}:${srcSellScore}->${targetBuyScore}:${targetSellScore} | len=$targetLen"
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
Write-Host "RP Market State Sync FORCE ALWAYS ATOMIC started"
Write-Host "IMPORTANT: Kill old sync scripts before running this one."
Write-Host "Source: $source"
Write-Host "Target: $target"
Write-Host "IntervalMs: $intervalMs | Retries: $maxRetries | RetrySleepMs: $retrySleepMs"
Write-Host "NO HASH GATING: sync runs every loop."
Write-Host "============================================================"

while ($true) {
    Sync-MarketStateAlwaysAtomic | Out-Null
    Start-Sleep -Milliseconds $intervalMs
}
