param(
    [Parameter(Mandatory=$true)]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedToken = "I_AUTHORIZE_P6_04_LIVE_ACTIVATION"
$ExpectedBranch = "prep/phase6-p6-02-p6-07"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedTaskName = "Hermes_Gateway_companion"
$ExpectedP603JobsSha256 = "3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5"
$ExpectedExecutionsSha256 = "a7a146921af20f97594258f4672c68e0c4955e7c1a1b361e857be8b4e470d208"
$ExpectedSchedulerSha256 = "6c0a43c175aab8e7d2a0107f6b067bcfa42f9a55650ab8cc761824c37fb02bfe"
$ExpectedOldColumns = "id,job_id,source,process_id,pid,process_started_at,status,claimed_at,started_at,finished_at,error"
$ExpectedNewColumns = "id,job_id,source,process_id,pid,process_started_at,status,claimed_at,started_at,finished_at,error,scheduled_at,delivery_outcome"

if ($AuthorizationToken -ne $ExpectedToken) {
    throw "STOP: explicit P6-04 live-activation authorization is required."
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

function Get-StatusLines([string]$Root) { return @(& git -C $Root status --porcelain=v1) }
function Get-StatusText([string]$Root) { return ((Get-StatusLines $Root) -join [Environment]::NewLine) }
function Assert-StatusEquals([string[]]$Actual, [string[]]$Expected, [string]$Label) {
    $ActualSorted = @($Actual | Sort-Object)
    $ExpectedSorted = @($Expected | Sort-Object)
    if (($ActualSorted -join "`n") -ne ($ExpectedSorted -join "`n")) {
        throw "STOP: $Label status mismatch. Actual: $($ActualSorted -join ' || ')"
    }
}
function Get-GatewayPid {
    if (-not (Test-Path -LiteralPath $PidPath)) { return $null }
    try {
        $Data = Get-Content -LiteralPath $PidPath -Raw | ConvertFrom-Json
        if ($null -eq $Data.pid) { return $null }
        return [int]$Data.pid
    }
    catch { return $null }
}
function Test-PidAlive([int]$ProcessId) {
    return ($null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue))
}
function Invoke-StateProbe {
    $Output = @(& $HermesPython -B $StateProbe --companion-home $CompanionHome)
    if ($LASTEXITCODE -ne 0) { throw "STOP: P6-04 production state probe failed." }
    return $Output
}
function Get-ProbeValue([string[]]$Output, [string]$Key) {
    $Prefix = $Key + "="
    $Line = @($Output | Where-Object { $_.StartsWith($Prefix) })
    if ($Line.Count -ne 1) { throw "STOP: expected one $Key line from state probe." }
    return $Line[0].Substring($Prefix.Length)
}

$RepoBranch = (& git -C $RepoRoot branch --show-current).Trim()
$RepoHeadBefore = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusBefore = Get-StatusText $RepoRoot
if ($RepoBranch -ne $ExpectedBranch) { throw "STOP: expected Orion branch $ExpectedBranch; observed $RepoBranch" }
if ($RepoStatusBefore) { throw "STOP: Orion worktree must be clean before P6-04 live activation." }

foreach ($Required in @($HermesRoot, $CompanionHome, $HermesPython, $StateProbe, $JobsTarget, $ExecutionsTarget, $SchedulerTarget)) {
    if (-not (Test-Path -LiteralPath $Required)) { throw "STOP: required P6-04 activation input missing: $Required" }
}

$HermesHeadBefore = (& git -C $HermesRoot rev-parse HEAD).Trim()
if ($HermesHeadBefore -ne $ExpectedHermesHead) { throw "STOP: Hermes pin drift." }

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
Assert-StatusEquals (Get-StatusLines $HermesRoot) $ExpectedHermesStatus "pre-activation Hermes"

$JobsSha = (Get-FileHash -LiteralPath $JobsTarget -Algorithm SHA256).Hash.ToLowerInvariant()
$ExecutionsSha = (Get-FileHash -LiteralPath $ExecutionsTarget -Algorithm SHA256).Hash.ToLowerInvariant()
$SchedulerSha = (Get-FileHash -LiteralPath $SchedulerTarget -Algorithm SHA256).Hash.ToLowerInvariant()
if ($JobsSha -ne $ExpectedP603JobsSha256) { throw "STOP: installed P6-03 cron/jobs.py hash drift." }
if ($ExecutionsSha -ne $ExpectedExecutionsSha256) { throw "STOP: installed P6-04 cron/executions.py hash drift." }
if ($SchedulerSha -ne $ExpectedSchedulerSha256) { throw "STOP: installed P6-04 cron/scheduler.py hash drift." }

$StateBefore = Invoke-StateProbe
$JobCountBefore = [int](Get-ProbeValue $StateBefore "P6_04_PROD_STATE_JOB_COUNT")
$RowsBefore = [int](Get-ProbeValue $StateBefore "P6_04_PROD_STATE_EXECUTION_ROWS")
$ColumnsBefore = Get-ProbeValue $StateBefore "P6_04_PROD_STATE_EXECUTION_COLUMNS"
if ($JobCountBefore -ne 0) { throw "STOP: COMPANION has $JobCountBefore cron job(s); live activation is blocked." }
if ($RowsBefore -ne 0) { throw "STOP: COMPANION executions.db contains $RowsBefore row(s); expected zero before activation." }
if ($ColumnsBefore -ne $ExpectedOldColumns) { throw "STOP: COMPANION schema is not the expected pre-activation schema." }

$Task = Get-ScheduledTask -TaskName $ExpectedTaskName -ErrorAction SilentlyContinue
if ($null -eq $Task) { throw "STOP: expected COMPANION Scheduled Task is missing." }
$StartupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$StartupVbs = Join-Path $StartupDir ($ExpectedTaskName + ".vbs")
$StartupCmd = Join-Path $StartupDir ($ExpectedTaskName + ".cmd")
if ((Test-Path -LiteralPath $StartupVbs) -or (Test-Path -LiteralPath $StartupCmd)) {
    throw "STOP: Startup fallback is present; supervisor state is ambiguous."
}

$OldPid = Get-GatewayPid
if ($null -eq $OldPid) { throw "STOP: no COMPANION gateway PID could be resolved." }
if (-not (Test-PidAlive $OldPid)) { throw "STOP: COMPANION gateway PID $OldPid is not alive." }
$OldProcess = Get-Process -Id $OldPid -ErrorAction Stop
$HeartbeatBefore = $null
if (Test-Path -LiteralPath $TickerHeartbeat) { $HeartbeatBefore = (Get-Item -LiteralPath $TickerHeartbeat).LastWriteTimeUtc }

Write-Host "P6_04_ACTIVATION_REPO_HEAD=$RepoHeadBefore"
Write-Host "P6_04_ACTIVATION_HERMES_HEAD=$HermesHeadBefore"
Write-Host "P6_04_ACTIVATION_TASK_NAME=$ExpectedTaskName"
Write-Host "P6_04_ACTIVATION_TASK_STATE=$($Task.State)"
Write-Host "P6_04_ACTIVATION_OLD_PID=$OldPid"
Write-Host "P6_04_ACTIVATION_OLD_PROCESS_START=$($OldProcess.StartTime.ToString('o'))"
Write-Host "P6_04_ACTIVATION_JOB_COUNT_BEFORE=$JobCountBefore"
Write-Host "P6_04_ACTIVATION_EXECUTION_ROWS_BEFORE=$RowsBefore"
Write-Host "P6_04_ACTIVATION_EXECUTION_COLUMNS_BEFORE=$ColumnsBefore"
Write-Host "P6_04_ACTIVATION_SOURCE_MUTATION_AUTHORIZED=false"
Write-Host "P6_04_ACTIVATION_REMINDER_MUTATION_AUTHORIZED=false"

$RestartStartUtc = [DateTime]::UtcNow
$OldHermesHome = $env:HERMES_HOME
$OldHermesProfile = $env:HERMES_PROFILE
try {
    $env:HERMES_HOME = $CompanionHome
    $env:HERMES_PROFILE = "companion"
    Push-Location $HermesRoot
    try {
        & $HermesPython -B -c "from hermes_cli import gateway_windows; gateway_windows.restart()"
        if ($LASTEXITCODE -ne 0) { throw "STOP: Hermes native Windows gateway restart returned non-zero." }
    }
    finally { Pop-Location }
}
finally {
    if ($null -eq $OldHermesHome) { Remove-Item Env:HERMES_HOME -ErrorAction SilentlyContinue } else { $env:HERMES_HOME = $OldHermesHome }
    if ($null -eq $OldHermesProfile) { Remove-Item Env:HERMES_PROFILE -ErrorAction SilentlyContinue } else { $env:HERMES_PROFILE = $OldHermesProfile }
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
if ($null -eq $NewPid) { throw "STOP: restart did not produce a new live COMPANION gateway PID within 30 seconds." }

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
if (-not $HeartbeatFresh) { throw "STOP: no fresh COMPANION ticker heartbeat was observed after restart." }

$SchemaDeadline = (Get-Date).AddSeconds(30)
$StateAfter = $null
while ((Get-Date) -lt $SchemaDeadline) {
    $CandidateState = Invoke-StateProbe
    $CandidateColumns = Get-ProbeValue $CandidateState "P6_04_PROD_STATE_EXECUTION_COLUMNS"
    if ($CandidateColumns -eq $ExpectedNewColumns) {
        $StateAfter = $CandidateState
        break
    }
    Start-Sleep -Milliseconds 500
}
if ($null -eq $StateAfter) { throw "STOP: P6-04 execution schema migration was not observed after restart." }

$JobCountAfter = [int](Get-ProbeValue $StateAfter "P6_04_PROD_STATE_JOB_COUNT")
$RowsAfter = [int](Get-ProbeValue $StateAfter "P6_04_PROD_STATE_EXECUTION_ROWS")
$ColumnsAfter = Get-ProbeValue $StateAfter "P6_04_PROD_STATE_EXECUTION_COLUMNS"
if ($JobCountAfter -ne 0) { throw "STOP: COMPANION jobs.json became non-empty during activation." }
if ($RowsAfter -ne 0) { throw "STOP: COMPANION execution row count changed during schema activation." }
if ($ColumnsAfter -ne $ExpectedNewColumns) { throw "STOP: COMPANION execution schema does not match expected P6-04 schema." }

$GatewayState = $null
if (Test-Path -LiteralPath $GatewayStatePath) {
    try {
        $State = Get-Content -LiteralPath $GatewayStatePath -Raw | ConvertFrom-Json
        $GatewayState = [string]$State.gateway_state
    }
    catch { throw "STOP: gateway_state.json exists but could not be parsed." }
}
if ($GatewayState -ne "running") { throw "STOP: gateway_state.json does not report running after activation." }

$RepoHeadAfter = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusAfter = Get-StatusText $RepoRoot
$HermesHeadAfter = (& git -C $HermesRoot rev-parse HEAD).Trim()
if ($RepoHeadAfter -ne $RepoHeadBefore -or $RepoStatusAfter -ne $RepoStatusBefore) { throw "STOP: Orion repository changed during live activation." }
if ($HermesHeadAfter -ne $HermesHeadBefore) { throw "STOP: Hermes HEAD changed during live activation." }
Assert-StatusEquals (Get-StatusLines $HermesRoot) $ExpectedHermesStatus "post-activation Hermes"
if ((Get-FileHash -LiteralPath $JobsTarget -Algorithm SHA256).Hash.ToLowerInvariant() -ne $JobsSha) { throw "STOP: cron/jobs.py changed during activation." }
if ((Get-FileHash -LiteralPath $ExecutionsTarget -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExecutionsSha) { throw "STOP: cron/executions.py changed during activation." }
if ((Get-FileHash -LiteralPath $SchedulerTarget -Algorithm SHA256).Hash.ToLowerInvariant() -ne $SchedulerSha) { throw "STOP: cron/scheduler.py changed during activation." }

Write-Host "P6_04_ACTIVATION_NEW_PID=$NewPid"
Write-Host "P6_04_ACTIVATION_NEW_PROCESS_START=$($NewProcess.StartTime.ToString('o'))"
Write-Host "P6_04_ACTIVATION_TICKER_HEARTBEAT_FRESH=true"
Write-Host "P6_04_ACTIVATION_JOB_COUNT_AFTER=$JobCountAfter"
Write-Host "P6_04_ACTIVATION_EXECUTION_ROWS_AFTER=$RowsAfter"
Write-Host "P6_04_ACTIVATION_EXECUTION_COLUMNS_AFTER=$ColumnsAfter"
Write-Host "P6_04_ACTIVATION_GATEWAY_STATE=$GatewayState"
Write-Host "P6_04_ACTIVATION_ORION_UNCHANGED=true"
Write-Host "P6_04_ACTIVATION_HERMES_HEAD_UNCHANGED=true"
Write-Host "P6_04_ACTIVATION_SOURCE_HASHES_UNCHANGED=true"
Write-Host "P6_04_ACTIVATION_REMINDER_CREATED=false"
Write-Host "P6_04_LIVE_ACTIVATION=PASS"
