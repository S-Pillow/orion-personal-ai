param(
    [Parameter(Mandatory=$true)]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedToken = "I_AUTHORIZE_P6_03_LIVE_ACTIVATION_START"
$ExpectedBranch = "prep/phase6-p6-02-p6-07"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedPatchedJobsSha256 = "3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5"
$ExpectedTaskName = "Hermes_Gateway_companion"

if ($AuthorizationToken -ne $ExpectedToken) {
    throw "STOP: explicit P6-03 live-activation start authorization is required."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$CompanionHome = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion"
$CompanionCron = Join-Path $CompanionHome "cron"
$JobsFile = Join-Path $CompanionCron "jobs.json"
$TickerHeartbeat = Join-Path $CompanionCron "ticker_heartbeat"
$PidPath = Join-Path $CompanionHome "gateway.pid"
$GatewayStatePath = Join-Path $CompanionHome "gateway_state.json"
$HermesPython = Join-Path $HermesRoot "venv\Scripts\python.exe"
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

function Test-PidAlive([int]$ProcessId) {
    return ($null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue))
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
        throw "STOP: COMPANION jobs.json is unreadable or malformed; live activation is blocked."
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
    throw "STOP: Orion worktree must be clean before P6-03 live activation."
}
if (-not (Test-Path -LiteralPath $HermesPython)) {
    throw "STOP: Hermes venv Python not found: $HermesPython"
}
if (-not (Test-Path -LiteralPath $CompanionHome)) {
    throw "STOP: COMPANION profile home not found: $CompanionHome"
}
if (-not (Test-Path -LiteralPath $Target)) {
    throw "STOP: installed Hermes cron/jobs.py not found: $Target"
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
Assert-StatusEquals $HermesStatusBefore $ExpectedHermesStatus "pre-activation Hermes"

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
    throw "STOP: Startup fallback is present; discovered supervisor state has changed."
}

$PrePid = Get-GatewayPid
if ($null -ne $PrePid -and (Test-PidAlive $PrePid)) {
    throw "STOP: a live COMPANION gateway already exists; start-only activation is not applicable."
}

if (Test-Path -LiteralPath $GatewayStatePath) {
    try {
        $State = Get-Content -LiteralPath $GatewayStatePath -Raw | ConvertFrom-Json
        if ([string]$State.gateway_state -ne "stopped") {
            throw "STOP: gateway_state.json no longer reports stopped; discovery state has changed."
        }
    }
    catch {
        throw
    }
}

$JobCountBefore = Get-CompanionJobCount
if ($JobCountBefore -ne 0) {
    throw "STOP: COMPANION has $JobCountBefore cron job(s); activation is blocked to avoid unintended reminder execution."
}

$HeartbeatBefore = $null
if (Test-Path -LiteralPath $TickerHeartbeat) {
    $HeartbeatBefore = (Get-Item -LiteralPath $TickerHeartbeat).LastWriteTimeUtc
}

Write-Host "P6_03_ACTIVATION_START_REPO_HEAD=$RepoHeadBefore"
Write-Host "P6_03_ACTIVATION_START_HERMES_HEAD=$HermesHeadBefore"
Write-Host "P6_03_ACTIVATION_START_PATCHED_JOBS_SHA256=$PatchedSha256"
Write-Host "P6_03_ACTIVATION_START_TASK_NAME=$ExpectedTaskName"
Write-Host "P6_03_ACTIVATION_START_TASK_STATE=$($Task.State)"
Write-Host "P6_03_ACTIVATION_START_JOB_COUNT_BEFORE=$JobCountBefore"
Write-Host "P6_03_ACTIVATION_START_PREEXISTING_LIVE_PID=false"
Write-Host "P6_03_ACTIVATION_START_SOURCE_MUTATION_AUTHORIZED=false"
Write-Host "P6_03_ACTIVATION_START_REMINDER_MUTATION_AUTHORIZED=false"

$StartUtc = [DateTime]::UtcNow
$OldHermesHome = $env:HERMES_HOME
$OldHermesProfile = $env:HERMES_PROFILE
try {
    $env:HERMES_HOME = $CompanionHome
    $env:HERMES_PROFILE = "companion"
    Push-Location $HermesRoot
    try {
        & $HermesPython -B -c "from hermes_cli import gateway_windows; gateway_windows.start()"
        if ($LASTEXITCODE -ne 0) {
            throw "STOP: Hermes native Windows gateway start returned non-zero."
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($null -eq $OldHermesHome) {
        Remove-Item Env:HERMES_HOME -ErrorAction SilentlyContinue
    }
    else {
        $env:HERMES_HOME = $OldHermesHome
    }
    if ($null -eq $OldHermesProfile) {
        Remove-Item Env:HERMES_PROFILE -ErrorAction SilentlyContinue
    }
    else {
        $env:HERMES_PROFILE = $OldHermesProfile
    }
}

$PidDeadline = (Get-Date).AddSeconds(30)
$NewPid = $null
while ((Get-Date) -lt $PidDeadline) {
    $Candidate = Get-GatewayPid
    if ($null -ne $Candidate -and (Test-PidAlive $Candidate)) {
        $NewPid = $Candidate
        break
    }
    Start-Sleep -Milliseconds 500
}
if ($null -eq $NewPid) {
    throw "STOP: start did not produce a live COMPANION gateway PID within 30 seconds."
}

$NewProcess = Get-Process -Id $NewPid -ErrorAction Stop
if ($NewProcess.StartTime.ToUniversalTime() -lt $StartUtc.AddSeconds(-2)) {
    throw "STOP: gateway PID has an unexpected pre-activation start time."
}

$HeartbeatFresh = $false
$HeartbeatDeadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $HeartbeatDeadline) {
    if (Test-Path -LiteralPath $TickerHeartbeat) {
        $NowHeartbeat = (Get-Item -LiteralPath $TickerHeartbeat).LastWriteTimeUtc
        $NewerThanBefore = ($null -eq $HeartbeatBefore) -or ($NowHeartbeat -gt $HeartbeatBefore)
        $AfterStart = ($NowHeartbeat -ge $StartUtc.AddSeconds(-2))
        if ($NewerThanBefore -and $AfterStart) {
            $HeartbeatFresh = $true
            break
        }
    }
    Start-Sleep -Seconds 2
}
if (-not $HeartbeatFresh) {
    throw "STOP: no fresh COMPANION ticker heartbeat was observed after gateway start."
}

$JobCountAfter = Get-CompanionJobCount
if ($JobCountAfter -ne 0) {
    throw "STOP: COMPANION jobs.json became non-empty during activation."
}

$RepoHeadAfter = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusAfter = Get-StatusText $RepoRoot
$HermesHeadAfter = (& git -C $HermesRoot rev-parse HEAD).Trim()
$HermesStatusAfter = Get-StatusLines $HermesRoot
$PatchedSha256After = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant()

if ($RepoHeadAfter -ne $RepoHeadBefore -or $RepoStatusAfter -ne $RepoStatusBefore) {
    throw "STOP: Orion repository changed during live activation."
}
if ($HermesHeadAfter -ne $HermesHeadBefore) {
    throw "STOP: Hermes HEAD changed during live activation."
}
Assert-StatusEquals $HermesStatusAfter $ExpectedHermesStatus "post-activation Hermes"
if ($PatchedSha256After -ne $ExpectedPatchedJobsSha256) {
    throw "STOP: patched cron/jobs.py changed during live activation."
}

Write-Host "P6_03_ACTIVATION_START_NEW_PID=$NewPid"
Write-Host "P6_03_ACTIVATION_START_NEW_PROCESS_START=$($NewProcess.StartTime.ToString('o'))"
Write-Host "P6_03_ACTIVATION_START_TICKER_HEARTBEAT_FRESH=true"
Write-Host "P6_03_ACTIVATION_START_JOB_COUNT_AFTER=$JobCountAfter"
Write-Host "P6_03_ACTIVATION_START_ORION_UNCHANGED=true"
Write-Host "P6_03_ACTIVATION_START_HERMES_HEAD_UNCHANGED=true"
Write-Host "P6_03_ACTIVATION_START_PATCH_HASH_UNCHANGED=true"
Write-Host "P6_03_ACTIVATION_START_REMINDER_CREATED=false"
Write-Host "P6_03_LIVE_ACTIVATION_START=PASS"
