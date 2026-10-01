param(
    [Parameter(Mandatory=$true)]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedToken = "I_AUTHORIZE_P6_04_LIVE_ACTIVATION_DISCOVERY"
$ExpectedBranch = "prep/phase6-p6-02-p6-07"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedP603JobsSha256 = "3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5"
$ExpectedExecutionsSha256 = "a7a146921af20f97594258f4672c68e0c4955e7c1a1b361e857be8b4e470d208"
$ExpectedSchedulerSha256 = "6c0a43c175aab8e7d2a0107f6b067bcfa42f9a55650ab8cc761824c37fb02bfe"
$ExpectedOldColumns = "id,job_id,source,process_id,pid,process_started_at,status,claimed_at,started_at,finished_at,error"

if ($AuthorizationToken -ne $ExpectedToken) {
    throw "STOP: explicit P6-04 live-activation discovery authorization is required."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$CompanionHome = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion"
$CompanionCron = Join-Path $CompanionHome "cron"
$HermesPython = Join-Path $HermesRoot "venv\Scripts\python.exe"
$StateProbe = Join-Path $PSScriptRoot "p6-04-production-state-probe.py"
$JobsTarget = Join-Path $HermesRoot "cron\jobs.py"
$ExecutionsTarget = Join-Path $HermesRoot "cron\executions.py"
$SchedulerTarget = Join-Path $HermesRoot "cron\scheduler.py"
$TickerHeartbeat = Join-Path $CompanionCron "ticker_heartbeat"
$PidPath = Join-Path $CompanionHome "gateway.pid"
$GatewayStatePath = Join-Path $CompanionHome "gateway_state.json"

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

function Invoke-StateProbe {
    $Output = @(& $HermesPython -B $StateProbe --companion-home $CompanionHome)
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: P6-04 production state probe failed."
    }
    return $Output
}

function Get-ProbeValue([string[]]$Output, [string]$Key) {
    $Prefix = $Key + "="
    $Line = @($Output | Where-Object { $_.StartsWith($Prefix) })
    if ($Line.Count -ne 1) {
        throw "STOP: expected one $Key line from state probe."
    }
    return $Line[0].Substring($Prefix.Length)
}

$RepoBranch = (& git -C $RepoRoot branch --show-current).Trim()
$RepoHeadBefore = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusBefore = Get-StatusText $RepoRoot

if ($RepoBranch -ne $ExpectedBranch) {
    throw "STOP: expected Orion branch $ExpectedBranch; observed $RepoBranch"
}
if ($RepoStatusBefore) {
    throw "STOP: Orion worktree must be clean before P6-04 live-activation discovery."
}

foreach ($Required in @($HermesRoot, $CompanionHome, $HermesPython, $StateProbe, $JobsTarget, $ExecutionsTarget, $SchedulerTarget)) {
    if (-not (Test-Path -LiteralPath $Required)) {
        throw "STOP: required P6-04 discovery input missing: $Required"
    }
}

$HermesHeadBefore = (& git -C $HermesRoot rev-parse HEAD).Trim()
if ($HermesHeadBefore -ne $ExpectedHermesHead) {
    throw "STOP: Hermes pin drift. Expected $ExpectedHermesHead; observed $HermesHeadBefore"
}

$ExpectedHermesStatus = @(
    " M cron/executions.py",
    " M cron/jobs.py",
    " M cron/scheduler.py",
    " M gateway/platforms/api_server.py",
    "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
    "?? gateway/platforms/api_server.py.orion-p4-04a.json",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json"
)
$HermesStatusBefore = Get-StatusLines $HermesRoot
Assert-StatusEquals $HermesStatusBefore $ExpectedHermesStatus "installed Hermes"

$JobsSha = (Get-FileHash -LiteralPath $JobsTarget -Algorithm SHA256).Hash.ToLowerInvariant()
$ExecutionsSha = (Get-FileHash -LiteralPath $ExecutionsTarget -Algorithm SHA256).Hash.ToLowerInvariant()
$SchedulerSha = (Get-FileHash -LiteralPath $SchedulerTarget -Algorithm SHA256).Hash.ToLowerInvariant()
if ($JobsSha -ne $ExpectedP603JobsSha256) { throw "STOP: installed P6-03 cron/jobs.py hash drift." }
if ($ExecutionsSha -ne $ExpectedExecutionsSha256) { throw "STOP: installed P6-04 cron/executions.py hash drift." }
if ($SchedulerSha -ne $ExpectedSchedulerSha256) { throw "STOP: installed P6-04 cron/scheduler.py hash drift." }

$StateBefore = Invoke-StateProbe
$StateBefore | ForEach-Object { Write-Host $_ }
$JobCount = [int](Get-ProbeValue $StateBefore "P6_04_PROD_STATE_JOB_COUNT")
$Columns = Get-ProbeValue $StateBefore "P6_04_PROD_STATE_EXECUTION_COLUMNS"
$Rows = [int](Get-ProbeValue $StateBefore "P6_04_PROD_STATE_EXECUTION_ROWS")
$SqliteMode = Get-ProbeValue $StateBefore "P6_04_PROD_STATE_SQLITE_MODE"
if ($JobCount -ne 0) { throw "STOP: COMPANION has $JobCount cron job(s); live activation discovery is not clean." }
if ($Rows -ne 0) { throw "STOP: COMPANION executions.db contains $Rows row(s); live activation discovery expected zero." }
if ($Columns -ne $ExpectedOldColumns) { throw "STOP: COMPANION execution schema changed before live activation. Observed: $Columns" }
if ($SqliteMode -ne "read_only") { throw "STOP: executions.db was not inspected read-only." }

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
    if ($null -eq $OldHermesHome) { Remove-Item Env:HERMES_HOME -ErrorAction SilentlyContinue } else { $env:HERMES_HOME = $OldHermesHome }
    if ($null -eq $OldHermesProfile) { Remove-Item Env:HERMES_PROFILE -ErrorAction SilentlyContinue } else { $env:HERMES_PROFILE = $OldHermesProfile }
}

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$TaskInfo = $null
if ($null -ne $Task) {
    $TaskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
}

$StartupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$StartupVbs = Join-Path $StartupDir ($TaskName + ".vbs")
$StartupCmd = Join-Path $StartupDir ($TaskName + ".cmd")

$GatewayPid = $null
if (Test-Path -LiteralPath $PidPath) {
    try {
        $PidData = Get-Content -LiteralPath $PidPath -Raw | ConvertFrom-Json
        if ($null -ne $PidData.pid) { $GatewayPid = [int]$PidData.pid }
    }
    catch {
        Write-Host "P6_04_ACTIVATION_DISCOVERY_PID_FILE_PARSE=FAIL"
    }
}

$GatewayProcess = $null
$GatewayCim = $null
if ($null -ne $GatewayPid) {
    $GatewayProcess = Get-Process -Id $GatewayPid -ErrorAction SilentlyContinue
    $GatewayCim = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $GatewayPid) -ErrorAction SilentlyContinue
}

$ParentRows = @()
$Seen = @{}
$CurrentCim = $GatewayCim
for ($i = 0; $i -lt 8 -and $null -ne $CurrentCim; $i++) {
    $CurrentProcessId = [int]$CurrentCim.ProcessId
    if ($Seen.ContainsKey($CurrentProcessId)) { break }
    $Seen[$CurrentProcessId] = $true
    $ParentRows += [pscustomobject]@{
        pid = $CurrentProcessId
        ppid = [int]$CurrentCim.ParentProcessId
        name = [string]$CurrentCim.Name
        executable = [string]$CurrentCim.ExecutablePath
    }
    if ([int]$CurrentCim.ParentProcessId -le 0) { break }
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

$GatewayState = $null
$GatewayStateUpdatedAt = $null
if (Test-Path -LiteralPath $GatewayStatePath) {
    try {
        $RawState = Get-Content -LiteralPath $GatewayStatePath -Raw | ConvertFrom-Json
        $GatewayState = [string]$RawState.gateway_state
        $GatewayStateUpdatedAt = [string]$RawState.updated_at
    }
    catch {
        Write-Host "P6_04_ACTIVATION_DISCOVERY_GATEWAY_STATE_PARSE=FAIL"
    }
}

$HeartbeatPresent = Test-Path -LiteralPath $TickerHeartbeat
$HeartbeatUtc = $null
if ($HeartbeatPresent) { $HeartbeatUtc = (Get-Item -LiteralPath $TickerHeartbeat).LastWriteTimeUtc }

Write-Host "P6_04_ACTIVATION_DISCOVERY_REPO_HEAD=$RepoHeadBefore"
Write-Host "P6_04_ACTIVATION_DISCOVERY_HERMES_HEAD=$HermesHeadBefore"
Write-Host "P6_04_ACTIVATION_DISCOVERY_JOBS_SHA256=$JobsSha"
Write-Host "P6_04_ACTIVATION_DISCOVERY_EXECUTIONS_SHA256=$ExecutionsSha"
Write-Host "P6_04_ACTIVATION_DISCOVERY_SCHEDULER_SHA256=$SchedulerSha"
Write-Host "P6_04_ACTIVATION_DISCOVERY_TASK_NAME=$TaskName"
Write-Host "P6_04_ACTIVATION_DISCOVERY_TASK_PRESENT=$($null -ne $Task)"
if ($null -ne $Task) {
    Write-Host "P6_04_ACTIVATION_DISCOVERY_TASK_STATE=$($Task.State)"
    Write-Host "P6_04_ACTIVATION_DISCOVERY_TASK_PATH=$($Task.TaskPath)"
}
if ($null -ne $TaskInfo) {
    Write-Host "P6_04_ACTIVATION_DISCOVERY_TASK_LAST_RESULT=$($TaskInfo.LastTaskResult)"
    Write-Host "P6_04_ACTIVATION_DISCOVERY_TASK_LAST_RUN=$($TaskInfo.LastRunTime.ToString('o'))"
}
Write-Host "P6_04_ACTIVATION_DISCOVERY_STARTUP_VBS_PRESENT=$(Test-Path -LiteralPath $StartupVbs)"
Write-Host "P6_04_ACTIVATION_DISCOVERY_STARTUP_CMD_PRESENT=$(Test-Path -LiteralPath $StartupCmd)"
Write-Host "P6_04_ACTIVATION_DISCOVERY_PID_FILE_PRESENT=$(Test-Path -LiteralPath $PidPath)"
Write-Host "P6_04_ACTIVATION_DISCOVERY_GATEWAY_PID=$GatewayPid"
Write-Host "P6_04_ACTIVATION_DISCOVERY_GATEWAY_PROCESS_PRESENT=$($null -ne $GatewayProcess)"
if ($null -ne $GatewayProcess) {
    Write-Host "P6_04_ACTIVATION_DISCOVERY_GATEWAY_PROCESS_NAME=$($GatewayProcess.ProcessName)"
    Write-Host "P6_04_ACTIVATION_DISCOVERY_GATEWAY_PROCESS_START=$($GatewayProcess.StartTime.ToString('o'))"
}
Write-Host "P6_04_ACTIVATION_DISCOVERY_PARENT_CHAIN_COUNT=$($ParentRows.Count)"
foreach ($Row in $ParentRows) {
    Write-Host ("P6_04_ACTIVATION_DISCOVERY_PARENT=pid:{0};ppid:{1};name:{2};exe:{3}" -f $Row.pid, $Row.ppid, $Row.name, $Row.executable)
}
Write-Host "P6_04_ACTIVATION_DISCOVERY_SERVICE_MATCH_COUNT=$($ServiceMatches.Count)"
foreach ($Svc in $ServiceMatches) {
    Write-Host ("P6_04_ACTIVATION_DISCOVERY_SERVICE=name:{0};state:{1};start_mode:{2};pid:{3}" -f $Svc.name, $Svc.state, $Svc.start_mode, $Svc.pid)
}
Write-Host "P6_04_ACTIVATION_DISCOVERY_GATEWAY_STATE_FILE_PRESENT=$(Test-Path -LiteralPath $GatewayStatePath)"
Write-Host "P6_04_ACTIVATION_DISCOVERY_GATEWAY_STATE=$GatewayState"
Write-Host "P6_04_ACTIVATION_DISCOVERY_GATEWAY_STATE_UPDATED_AT=$GatewayStateUpdatedAt"
Write-Host "P6_04_ACTIVATION_DISCOVERY_TICKER_HEARTBEAT_PRESENT=$HeartbeatPresent"
if ($HeartbeatPresent) { Write-Host "P6_04_ACTIVATION_DISCOVERY_TICKER_HEARTBEAT_UTC=$($HeartbeatUtc.ToString('o'))" }
Write-Host "P6_04_ACTIVATION_DISCOVERY_JOB_COUNT=$JobCount"
Write-Host "P6_04_ACTIVATION_DISCOVERY_EXECUTION_ROWS=$Rows"
Write-Host "P6_04_ACTIVATION_DISCOVERY_EXECUTION_COLUMNS=$Columns"

$RepoHeadAfter = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusAfter = Get-StatusText $RepoRoot
$HermesHeadAfter = (& git -C $HermesRoot rev-parse HEAD).Trim()
$HermesStatusAfter = Get-StatusLines $HermesRoot
$JobsShaAfter = (Get-FileHash -LiteralPath $JobsTarget -Algorithm SHA256).Hash.ToLowerInvariant()
$ExecutionsShaAfter = (Get-FileHash -LiteralPath $ExecutionsTarget -Algorithm SHA256).Hash.ToLowerInvariant()
$SchedulerShaAfter = (Get-FileHash -LiteralPath $SchedulerTarget -Algorithm SHA256).Hash.ToLowerInvariant()
$StateAfter = Invoke-StateProbe

if ($RepoHeadAfter -ne $RepoHeadBefore -or $RepoStatusAfter -ne $RepoStatusBefore) { throw "STOP: Orion repository changed during P6-04 live-activation discovery." }
if ($HermesHeadAfter -ne $HermesHeadBefore) { throw "STOP: Hermes HEAD changed during P6-04 live-activation discovery." }
Assert-StatusEquals $HermesStatusAfter $ExpectedHermesStatus "post-discovery Hermes"
if ($JobsShaAfter -ne $JobsSha -or $ExecutionsShaAfter -ne $ExecutionsSha -or $SchedulerShaAfter -ne $SchedulerSha) { throw "STOP: installed compatibility source changed during discovery." }
if ((Get-ProbeValue $StateAfter "P6_04_PROD_STATE_JOB_COUNT") -ne "0") { throw "STOP: COMPANION job count changed during discovery." }
if ((Get-ProbeValue $StateAfter "P6_04_PROD_STATE_EXECUTION_ROWS") -ne "0") { throw "STOP: COMPANION execution row count changed during discovery." }
if ((Get-ProbeValue $StateAfter "P6_04_PROD_STATE_EXECUTION_COLUMNS") -ne $ExpectedOldColumns) { throw "STOP: COMPANION execution schema changed during discovery." }

Write-Host "P6_04_ACTIVATION_DISCOVERY_ORION_UNCHANGED=true"
Write-Host "P6_04_ACTIVATION_DISCOVERY_HERMES_UNCHANGED=true"
Write-Host "P6_04_ACTIVATION_DISCOVERY_COMPANION_STATE_UNCHANGED=true"
Write-Host "P6_04_ACTIVATION_DISCOVERY_RESTART_PERFORMED=false"
Write-Host "P6_04_ACTIVATION_DISCOVERY_REMINDER_CREATED=false"
Write-Host "P6_04_LIVE_ACTIVATION_DISCOVERY=PASS"
