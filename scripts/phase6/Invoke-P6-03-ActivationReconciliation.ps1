param(
    [Parameter(Mandatory=$true)]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedToken = "I_AUTHORIZE_P6_03_ACTIVATION_RECONCILIATION"
$ExpectedBranch = "prep/phase6-p6-02-p6-07"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedPatchedJobsSha256 = "3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5"
$ExpectedTaskName = "Hermes_Gateway_companion"

if ($AuthorizationToken -ne $ExpectedToken) {
    throw "STOP: explicit P6-03 activation reconciliation authorization is required."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$CompanionHome = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion"
$CompanionCron = Join-Path $CompanionHome "cron"
$JobsFile = Join-Path $CompanionCron "jobs.json"
$TickerHeartbeat = Join-Path $CompanionCron "ticker_heartbeat"
$PidPath = Join-Path $CompanionHome "gateway.pid"
$GatewayStatePath = Join-Path $CompanionHome "gateway_state.json"
$Target = Join-Path $HermesRoot "cron\jobs.py"

function Get-StatusLines([string]$Root) {
    return @(& git -C $Root status --porcelain=v1)
}

function Get-StatusText([string]$Root) {
    return ((Get-StatusLines $Root) -join [Environment]::NewLine)
}

function Assert-StatusEquals([string[]]$Actual, [string[]]$Expected, [string]$Label) {
    $ActualSorted = @($Actual | Sort-Object)
    $ExpectedSorted = @($Expected | Sort-Object)
    if (($ActualSorted -join "`n") -ne ($ExpectedSorted -join "`n")) {
        throw "STOP: $Label status mismatch. Actual: $($ActualSorted -join ' || ')"
    }
}

function Get-GatewayPid {
    if (-not (Test-Path -LiteralPath $PidPath)) {
        return $null
    }
    try {
        $Data = Get-Content -LiteralPath $PidPath -Raw | ConvertFrom-Json
        if ($null -eq $Data.pid) {
            return $null
        }
        return [int]$Data.pid
    }
    catch {
        return $null
    }
}

function Get-CompanionJobCount {
    if (-not (Test-Path -LiteralPath $JobsFile)) {
        return 0
    }

    try {
        $Raw = Get-Content -LiteralPath $JobsFile -Raw -Encoding UTF8
        $Data = $Raw | ConvertFrom-Json
    }
    catch {
        throw "STOP: COMPANION jobs.json is unreadable or malformed."
    }

    if ($Data -is [System.Array]) {
        return @($Data).Count
    }

    if ($null -eq $Data.jobs) {
        throw "STOP: COMPANION jobs.json is not canonical and has no jobs field."
    }

    return @($Data.jobs).Count
}

$RepoBranch = (& git -C $RepoRoot branch --show-current).Trim()
$RepoHeadBefore = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusBefore = Get-StatusText $RepoRoot

if ($RepoBranch -ne $ExpectedBranch) {
    throw "STOP: expected Orion branch $ExpectedBranch; observed $RepoBranch"
}
if ($RepoStatusBefore) {
    throw "STOP: Orion worktree must be clean before P6-03 activation reconciliation."
}

$HermesHeadBefore = (& git -C $HermesRoot rev-parse HEAD).Trim()
if ($HermesHeadBefore -ne $ExpectedHermesHead) {
    throw "STOP: Hermes pin drift. Expected $ExpectedHermesHead; observed $HermesHeadBefore"
}

$ExpectedHermesStatus = @(
    " M cron/jobs.py",
    " M gateway/platforms/api_server.py",
    "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
    "?? gateway/platforms/api_server.py.orion-p4-04a.json",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json"
)
$HermesStatusBefore = Get-StatusLines $HermesRoot
Assert-StatusEquals $HermesStatusBefore $ExpectedHermesStatus "Hermes"

$PatchedSha256 = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant()
if ($PatchedSha256 -ne $ExpectedPatchedJobsSha256) {
    throw "STOP: installed P6-03 cron/jobs.py hash drift. Expected $ExpectedPatchedJobsSha256; observed $PatchedSha256"
}

$Task = Get-ScheduledTask -TaskName $ExpectedTaskName -ErrorAction SilentlyContinue
if ($null -eq $Task) {
    throw "STOP: expected COMPANION Scheduled Task is missing."
}

$StartupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$StartupVbs = Join-Path $StartupDir ($ExpectedTaskName + ".vbs")
$StartupCmd = Join-Path $StartupDir ($ExpectedTaskName + ".cmd")
if ((Test-Path -LiteralPath $StartupVbs) -or (Test-Path -LiteralPath $StartupCmd)) {
    throw "STOP: Startup fallback is present; supervisor state is ambiguous."
}

$GatewayPid = Get-GatewayPid
if ($null -eq $GatewayPid) {
    throw "STOP: no COMPANION gateway PID file could be resolved after the attempted activation."
}

$GatewayProcess = Get-Process -Id $GatewayPid -ErrorAction SilentlyContinue
if ($null -eq $GatewayProcess) {
    throw "STOP: COMPANION gateway PID $GatewayPid is not alive."
}

$ProcessStartUtc = $GatewayProcess.StartTime.ToUniversalTime()

if (-not (Test-Path -LiteralPath $TickerHeartbeat)) {
    throw "STOP: COMPANION ticker heartbeat file is missing."
}

$HeartbeatUtc = (Get-Item -LiteralPath $TickerHeartbeat).LastWriteTimeUtc
if ($HeartbeatUtc -lt $ProcessStartUtc.AddSeconds(-2)) {
    throw "STOP: ticker heartbeat predates the live gateway process start; activation is not proven."
}

$JobCount = Get-CompanionJobCount
if ($JobCount -ne 0) {
    throw "STOP: COMPANION has $JobCount cron job(s); activation reconciliation is not clean."
}

$GatewayState = $null
$GatewayStateUpdatedAt = $null
if (Test-Path -LiteralPath $GatewayStatePath) {
    try {
        $State = Get-Content -LiteralPath $GatewayStatePath -Raw | ConvertFrom-Json
        $GatewayState = [string]$State.gateway_state
        $GatewayStateUpdatedAt = [string]$State.updated_at
    }
    catch {
        throw "STOP: gateway_state.json exists but could not be parsed."
    }
}

$RepoHeadAfter = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusAfter = Get-StatusText $RepoRoot
$HermesHeadAfter = (& git -C $HermesRoot rev-parse HEAD).Trim()
$HermesStatusAfter = Get-StatusLines $HermesRoot
$PatchedSha256After = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant()

if ($RepoHeadAfter -ne $RepoHeadBefore -or $RepoStatusAfter -ne $RepoStatusBefore) {
    throw "STOP: Orion repository changed during reconciliation."
}
if ($HermesHeadAfter -ne $HermesHeadBefore) {
    throw "STOP: Hermes HEAD changed during reconciliation."
}
Assert-StatusEquals $HermesStatusAfter $ExpectedHermesStatus "post-reconciliation Hermes"
if ($PatchedSha256After -ne $ExpectedPatchedJobsSha256) {
    throw "STOP: patched cron/jobs.py changed during reconciliation."
}

Write-Host "P6_03_RECONCILE_REPO_HEAD=$RepoHeadBefore"
Write-Host "P6_03_RECONCILE_HERMES_HEAD=$HermesHeadBefore"
Write-Host "P6_03_RECONCILE_PATCHED_JOBS_SHA256=$PatchedSha256"
Write-Host "P6_03_RECONCILE_TASK_NAME=$ExpectedTaskName"
Write-Host "P6_03_RECONCILE_TASK_STATE=$($Task.State)"
Write-Host "P6_03_RECONCILE_GATEWAY_PID=$GatewayPid"
Write-Host "P6_03_RECONCILE_GATEWAY_PROCESS_START=$($GatewayProcess.StartTime.ToString('o'))"
Write-Host "P6_03_RECONCILE_TICKER_HEARTBEAT_UTC=$($HeartbeatUtc.ToString('o'))"
Write-Host "P6_03_RECONCILE_TICKER_HEARTBEAT_AFTER_PROCESS_START=true"
Write-Host "P6_03_RECONCILE_JOB_COUNT=$JobCount"
Write-Host "P6_03_RECONCILE_GATEWAY_STATE=$GatewayState"
Write-Host "P6_03_RECONCILE_GATEWAY_STATE_UPDATED_AT=$GatewayStateUpdatedAt"
Write-Host "P6_03_RECONCILE_ORION_UNCHANGED=true"
Write-Host "P6_03_RECONCILE_HERMES_UNCHANGED=true"
Write-Host "P6_03_RECONCILE_PATCH_HASH_UNCHANGED=true"
Write-Host "P6_03_RECONCILE_REMINDER_CREATED=false"
Write-Host "P6_03_ACTIVATION_RECONCILIATION=PASS"
