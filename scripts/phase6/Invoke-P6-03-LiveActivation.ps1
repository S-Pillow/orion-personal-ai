param(
    [Parameter(Mandatory=$true)]
    [string]$AuthorizationToken,

    [Parameter(Mandatory=$true)]
    [ValidateSet("windows-scheduled-task", "windows-startup")]
    [string]$ExpectedSupervisorMode
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedToken = "I_AUTHORIZE_P6_03_LIVE_ACTIVATION"
$ExpectedBranch = "prep/phase6-p6-02-p6-07"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedPatchedJobsSha256 = "3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5"

if ($AuthorizationToken -ne $ExpectedToken) {
    throw "STOP: explicit P6-03 live-activation authorization is required."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$CompanionHome = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion"
$CompanionCron = Join-Path $CompanionHome "cron"
$JobsFile = Join-Path $CompanionCron "jobs.json"
$TickerHeartbeat = Join-Path $CompanionCron "ticker_heartbeat"
$PidPath = Join-Path $CompanionHome "gateway.pid"
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

function Test-PidAlive([int]$Pid) {
    return ($null -ne (Get-Process -Id $Pid -ErrorAction SilentlyContinue))
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

$JobCountBefore = Get-CompanionJobCount
if ($JobCountBefore -ne 0) {
    throw "STOP: COMPANION has $JobCountBefore cron job(s); live activation is blocked to avoid unintended reminder execution."
}

$OldHermesHome = $env:HERMES_HOME
$OldHermesProfile = $env:HERMES_PROFILE
try {
    $env:HERMES_HOME = $CompanionHome
    $env:HERMES_PROFILE = "companion"
    Push-Location $HermesRoot
    try {
        $TaskName = (& $HermesPython -B -c "from hermes_cli.gateway_windows import get_task_name; print(get_task_name())").Trim()
        if ($LASTEXITCODE -ne 0 -or -not $TaskName) {
            throw "STOP: could not resolve Hermes Windows task name for COMPANION."
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

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$StartupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$StartupVbs = Join-Path $StartupDir ($TaskName + ".vbs")
$StartupCmd = Join-Path $StartupDir ($TaskName + ".cmd")
$StartupPresent = (Test-Path -LiteralPath $StartupVbs) -or (Test-Path -LiteralPath $StartupCmd)

if ($null -ne $Task -and $StartupPresent) {
    throw "STOP: both Scheduled Task and Startup fallback are present; supervisor ownership is ambiguous."
}

$ObservedSupervisorMode = $null
if ($null -ne $Task) {
    $ObservedSupervisorMode = "windows-scheduled-task"
}
elseif ($StartupPresent) {
    $ObservedSupervisorMode = "windows-startup"
}
else {
    throw "STOP: no supported Hermes Windows persistence mechanism is present. Do not use the generic live-activation script."
}

if ($ObservedSupervisorMode -ne $ExpectedSupervisorMode) {
    throw "STOP: supervisor mode mismatch. Expected $ExpectedSupervisorMode; observed $ObservedSupervisorMode"
}

$OldPid = Get-GatewayPid
if ($null -eq $OldPid) {
    throw "STOP: no COMPANION gateway PID could be resolved."
}
if (-not (Test-PidAlive $OldPid)) {
    throw "STOP: COMPANION gateway PID $OldPid is not alive."
}

$OldProcess = Get-Process -Id $OldPid -ErrorAction Stop
$OldProcessStart = $OldProcess.StartTime

$HeartbeatBefore = $null
if (Test-Path -LiteralPath $TickerHeartbeat) {
    $HeartbeatBefore = (Get-Item -LiteralPath $TickerHeartbeat).LastWriteTimeUtc
}

Write-Host "P6_03_ACTIVATION_REPO_HEAD=$RepoHeadBefore"
Write-Host "P6_03_ACTIVATION_HERMES_HEAD=$HermesHeadBefore"
Write-Host "P6_03_ACTIVATION_PATCHED_JOBS_SHA256=$PatchedSha256"
Write-Host "P6_03_ACTIVATION_SUPERVISOR_MODE=$ObservedSupervisorMode"
Write-Host "P6_03_ACTIVATION_TASK_NAME=$TaskName"
Write-Host "P6_03_ACTIVATION_OLD_PID=$OldPid"
Write-Host "P6_03_ACTIVATION_OLD_PROCESS_START=$($OldProcessStart.ToString('o'))"
Write-Host "P6_03_ACTIVATION_JOB_COUNT_BEFORE=$JobCountBefore"
Write-Host "P6_03_ACTIVATION_SOURCE_MUTATION_AUTHORIZED=false"
Write-Host "P6_03_ACTIVATION_REMINDER_MUTATION_AUTHORIZED=false"

$RestartStartUtc = [DateTime]::UtcNow

$OldHermesHome = $env:HERMES_HOME
$OldHermesProfile = $env:HERMES_PROFILE
try {
    $env:HERMES_HOME = $CompanionHome
    $env:HERMES_PROFILE = "companion"
    Push-Location $HermesRoot
    try {
        & $HermesPython -B -c "from hermes_cli import gateway_windows; gateway_windows.restart()"
        if ($LASTEXITCODE -ne 0) {
            throw "STOP: Hermes native Windows gateway restart returned non-zero."
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

$Deadline = (Get-Date).AddSeconds(30)
$NewPid = $null
while ((Get-Date) -lt $Deadline) {
    $Candidate = Get-GatewayPid
    if ($null -ne $Candidate -and $Candidate -ne $OldPid -and (Test-PidAlive $Candidate)) {
        $NewPid = $Candidate
        break
    }
    Start-Sleep -Milliseconds 500
}
if ($null -eq $NewPid) {
    throw "STOP: restart did not produce a new live COMPANION gateway PID within 30 seconds."
}

$NewProcess = Get-Process -Id $NewPid -ErrorAction Stop
if ($NewProcess.StartTime.ToUniversalTime() -lt $RestartStartUtc.AddSeconds(-2)) {
    throw "STOP: new gateway PID has an unexpected pre-restart start time."
}

$HeartbeatFresh = $false
$HeartbeatDeadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $HeartbeatDeadline) {
    if (Test-Path -LiteralPath $TickerHeartbeat) {
        $NowHeartbeat = (Get-Item -LiteralPath $TickerHeartbeat).LastWriteTimeUtc
        $NewerThanBefore = ($null -eq $HeartbeatBefore) -or ($NowHeartbeat -gt $HeartbeatBefore)
        $AfterRestart = ($NowHeartbeat -ge $RestartStartUtc.AddSeconds(-2))
        if ($NewerThanBefore -and $AfterRestart) {
            $HeartbeatFresh = $true
            break
        }
    }
    Start-Sleep -Seconds 2
}
if (-not $HeartbeatFresh) {
    throw "STOP: no fresh COMPANION ticker heartbeat was observed after restart."
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

Write-Host "P6_03_ACTIVATION_NEW_PID=$NewPid"
Write-Host "P6_03_ACTIVATION_NEW_PROCESS_START=$($NewProcess.StartTime.ToString('o'))"
Write-Host "P6_03_ACTIVATION_TICKER_HEARTBEAT_FRESH=true"
Write-Host "P6_03_ACTIVATION_JOB_COUNT_AFTER=$JobCountAfter"
Write-Host "P6_03_ACTIVATION_ORION_UNCHANGED=true"
Write-Host "P6_03_ACTIVATION_HERMES_HEAD_UNCHANGED=true"
Write-Host "P6_03_ACTIVATION_PATCH_HASH_UNCHANGED=true"
Write-Host "P6_03_ACTIVATION_REMINDER_CREATED=false"
Write-Host "P6_03_LIVE_ACTIVATION=PASS"
