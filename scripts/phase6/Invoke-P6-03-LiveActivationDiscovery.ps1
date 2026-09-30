param(
    [Parameter(Mandatory=$true)]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedToken = "I_AUTHORIZE_P6_03_LIVE_ACTIVATION_DISCOVERY"
$ExpectedBranch = "prep/phase6-p6-02-p6-07"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedPatchedJobsSha256 = "3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5"

if ($AuthorizationToken -ne $ExpectedToken) {
    throw "STOP: explicit P6-03 live-activation discovery authorization is required."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$CompanionHome = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion"
$CompanionCron = Join-Path $CompanionHome "cron"
$HermesPython = Join-Path $HermesRoot "venv\Scripts\python.exe"
$Target = Join-Path $HermesRoot "cron\jobs.py"

function Get-StatusLines([string]$Root) {
    return @(& git -C $Root status --porcelain=v1)
}

function Get-StatusText([string]$Root) {
    return ((Get-StatusLines $Root) -join [Environment]::NewLine)
}

function Get-CronMetadata([string]$CronPath) {
    if (-not (Test-Path -LiteralPath $CronPath)) {
        return @()
    }
    return @(
        Get-ChildItem -LiteralPath $CronPath -Force |
            Sort-Object Name |
            ForEach-Object {
                $Type = if ($_.PSIsContainer) { "DIR" } else { "FILE" }
                $Length = if ($_.PSIsContainer) { 0 } else { $_.Length }
                "{0}|{1}|{2}|{3}" -f $_.Name, $Type, $Length, $_.LastWriteTimeUtc.Ticks
            }
    )
}

function Assert-StatusEquals([string[]]$Actual, [string[]]$Expected, [string]$Label) {
    $ActualSorted = @($Actual | Sort-Object)
    $ExpectedSorted = @($Expected | Sort-Object)
    if (($ActualSorted -join "`n") -ne ($ExpectedSorted -join "`n")) {
        throw "STOP: $Label status mismatch. Actual: $($ActualSorted -join ' || ')"
    }
}

$RepoBranch = (& git -C $RepoRoot branch --show-current).Trim()
$RepoHeadBefore = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusBefore = Get-StatusText $RepoRoot

if ($RepoBranch -ne $ExpectedBranch) {
    throw "STOP: expected Orion branch $ExpectedBranch; observed $RepoBranch"
}
if ($RepoStatusBefore) {
    throw "STOP: Orion worktree must be clean before P6-03 live-activation discovery."
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
Assert-StatusEquals $HermesStatusBefore $ExpectedHermesStatus "installed Hermes"

$PatchedSha256 = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant()
if ($PatchedSha256 -ne $ExpectedPatchedJobsSha256) {
    throw "STOP: installed P6-03 cron/jobs.py hash drift. Expected $ExpectedPatchedJobsSha256; observed $PatchedSha256"
}

$CompanionBefore = Get-CronMetadata $CompanionCron

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
$TaskInfo = $null
if ($null -ne $Task) {
    $TaskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
}

$StartupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$StartupVbs = Join-Path $StartupDir ($TaskName + ".vbs")
$StartupCmd = Join-Path $StartupDir ($TaskName + ".cmd")

$PidPath = Join-Path $CompanionHome "gateway.pid"
$GatewayPid = $null
if (Test-Path -LiteralPath $PidPath) {
    try {
        $PidData = Get-Content -LiteralPath $PidPath -Raw | ConvertFrom-Json
        if ($null -ne $PidData.pid) {
            $GatewayPid = [int]$PidData.pid
        }
    }
    catch {
        Write-Host "P6_03_ACTIVATION_DISCOVERY_PID_FILE_PARSE=FAIL"
    }
}

$GatewayProcess = $null
$GatewayCim = $null
if ($null -ne $GatewayPid) {
    $GatewayProcess = Get-Process -Id $GatewayPid -ErrorAction SilentlyContinue
    $GatewayCim = Get-CimInstance Win32_Process -Filter "ProcessId=$GatewayPid" -ErrorAction SilentlyContinue
}

$ParentRows = @()
$Seen = @{}
$CurrentCim = $GatewayCim
for ($i = 0; $i -lt 8 -and $null -ne $CurrentCim; $i++) {
    $CurrentPid = [int]$CurrentCim.ProcessId
    if ($Seen.ContainsKey($CurrentPid)) {
        break
    }
    $Seen[$CurrentPid] = $true
    $ParentRows += [pscustomobject]@{
        pid = $CurrentPid
        ppid = [int]$CurrentCim.ParentProcessId
        name = [string]$CurrentCim.Name
        executable = [string]$CurrentCim.ExecutablePath
    }
    if ([int]$CurrentCim.ParentProcessId -le 0) {
        break
    }
    $CurrentCim = Get-CimInstance Win32_Process -Filter ("ProcessId=" + [int]$CurrentCim.ParentProcessId) -ErrorAction SilentlyContinue
}

$ServiceMatches = @()
foreach ($Row in $ParentRows) {
    $Svc = Get-CimInstance Win32_Service -Filter ("ProcessId=" + [int]$Row.pid) -ErrorAction SilentlyContinue
    if ($null -ne $Svc) {
        foreach ($S in @($Svc)) {
            $ServiceMatches += [pscustomobject]@{
                name = [string]$S.Name
                state = [string]$S.State
                start_mode = [string]$S.StartMode
                pid = [int]$S.ProcessId
            }
        }
    }
}

$GatewayStatePath = Join-Path $CompanionHome "gateway_state.json"
$GatewayState = $null
if (Test-Path -LiteralPath $GatewayStatePath) {
    try {
        $RawState = Get-Content -LiteralPath $GatewayStatePath -Raw | ConvertFrom-Json
        $GatewayState = [pscustomobject]@{
            gateway_state = [string]$RawState.gateway_state
            updated_at = [string]$RawState.updated_at
        }
    }
    catch {
        Write-Host "P6_03_ACTIVATION_DISCOVERY_GATEWAY_STATE_PARSE=FAIL"
    }
}

Write-Host "P6_03_ACTIVATION_DISCOVERY_REPO_HEAD=$RepoHeadBefore"
Write-Host "P6_03_ACTIVATION_DISCOVERY_HERMES_HEAD=$HermesHeadBefore"
Write-Host "P6_03_ACTIVATION_DISCOVERY_PATCHED_JOBS_SHA256=$PatchedSha256"
Write-Host "P6_03_ACTIVATION_DISCOVERY_COMPANION_HOME=$CompanionHome"
Write-Host "P6_03_ACTIVATION_DISCOVERY_TASK_NAME=$TaskName"
Write-Host "P6_03_ACTIVATION_DISCOVERY_TASK_PRESENT=$($null -ne $Task)"
if ($null -ne $Task) {
    Write-Host "P6_03_ACTIVATION_DISCOVERY_TASK_STATE=$($Task.State)"
    Write-Host "P6_03_ACTIVATION_DISCOVERY_TASK_PATH=$($Task.TaskPath)"
}
if ($null -ne $TaskInfo) {
    Write-Host "P6_03_ACTIVATION_DISCOVERY_TASK_LAST_RESULT=$($TaskInfo.LastTaskResult)"
    Write-Host "P6_03_ACTIVATION_DISCOVERY_TASK_LAST_RUN=$($TaskInfo.LastRunTime.ToString('o'))"
}
Write-Host "P6_03_ACTIVATION_DISCOVERY_STARTUP_VBS_PRESENT=$(Test-Path -LiteralPath $StartupVbs)"
Write-Host "P6_03_ACTIVATION_DISCOVERY_STARTUP_CMD_PRESENT=$(Test-Path -LiteralPath $StartupCmd)"
Write-Host "P6_03_ACTIVATION_DISCOVERY_PID_FILE_PRESENT=$(Test-Path -LiteralPath $PidPath)"
Write-Host "P6_03_ACTIVATION_DISCOVERY_GATEWAY_PID=$GatewayPid"
Write-Host "P6_03_ACTIVATION_DISCOVERY_GATEWAY_PROCESS_PRESENT=$($null -ne $GatewayProcess)"
if ($null -ne $GatewayProcess) {
    Write-Host "P6_03_ACTIVATION_DISCOVERY_GATEWAY_PROCESS_NAME=$($GatewayProcess.ProcessName)"
    Write-Host "P6_03_ACTIVATION_DISCOVERY_GATEWAY_PROCESS_START=$($GatewayProcess.StartTime.ToString('o'))"
}
Write-Host "P6_03_ACTIVATION_DISCOVERY_PARENT_CHAIN_COUNT=$($ParentRows.Count)"
foreach ($Row in $ParentRows) {
    Write-Host ("P6_03_ACTIVATION_DISCOVERY_PARENT=pid:{0};ppid:{1};name:{2};exe:{3}" -f $Row.pid, $Row.ppid, $Row.name, $Row.executable)
}
Write-Host "P6_03_ACTIVATION_DISCOVERY_SERVICE_MATCH_COUNT=$($ServiceMatches.Count)"
foreach ($Svc in $ServiceMatches) {
    Write-Host ("P6_03_ACTIVATION_DISCOVERY_SERVICE=name:{0};state:{1};start_mode:{2};pid:{3}" -f $Svc.name, $Svc.state, $Svc.start_mode, $Svc.pid)
}
Write-Host "P6_03_ACTIVATION_DISCOVERY_GATEWAY_STATE_FILE_PRESENT=$(Test-Path -LiteralPath $GatewayStatePath)"
if ($null -ne $GatewayState) {
    Write-Host "P6_03_ACTIVATION_DISCOVERY_GATEWAY_STATE=$($GatewayState.gateway_state)"
    Write-Host "P6_03_ACTIVATION_DISCOVERY_GATEWAY_STATE_UPDATED_AT=$($GatewayState.updated_at)"
}

$RepoHeadAfter = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusAfter = Get-StatusText $RepoRoot
$HermesHeadAfter = (& git -C $HermesRoot rev-parse HEAD).Trim()
$HermesStatusAfter = Get-StatusLines $HermesRoot
$CompanionAfter = Get-CronMetadata $CompanionCron

if ($RepoHeadAfter -ne $RepoHeadBefore -or $RepoStatusAfter -ne $RepoStatusBefore) {
    throw "STOP: Orion repository changed during live-activation discovery."
}
if ($HermesHeadAfter -ne $HermesHeadBefore) {
    throw "STOP: Hermes HEAD changed during live-activation discovery."
}
Assert-StatusEquals $HermesStatusAfter $ExpectedHermesStatus "post-discovery Hermes"
if (($CompanionAfter -join [Environment]::NewLine) -ne ($CompanionBefore -join [Environment]::NewLine)) {
    throw "STOP: COMPANION cron metadata changed during live-activation discovery."
}

Write-Host "P6_03_ACTIVATION_DISCOVERY_ORION_UNCHANGED=true"
Write-Host "P6_03_ACTIVATION_DISCOVERY_HERMES_UNCHANGED=true"
Write-Host "P6_03_ACTIVATION_DISCOVERY_COMPANION_CRON_UNCHANGED=true"
Write-Host "P6_03_ACTIVATION_DISCOVERY_RESTART_PERFORMED=false"
Write-Host "P6_03_LIVE_ACTIVATION_DISCOVERY=PASS"
