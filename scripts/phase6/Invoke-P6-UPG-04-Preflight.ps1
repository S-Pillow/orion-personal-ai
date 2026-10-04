param(
    [string]$OrionRepo = "D:\Orion\orion-personal-ai",
    [string]$HermesHome = "$env:LOCALAPPDATA\hermes",
    [string]$CompanionHome = "$env:LOCALAPPDATA\hermes\profiles\companion",
    [string]$InstalledHermesRoot = "$env:LOCALAPPDATA\hermes\hermes-agent",
    [int]$GatewayPort = 8642,
    [ValidateSet("OPEN_UNRESOLVED", "QUALIFIED_FIX_INCLUDED")]
    [string]$VendorWarmupDisposition = "OPEN_UNRESOLVED"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedOrionBranch = "feature/p6-upg-04-controlled-production-upgrade"
$ExpectedInstalledHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedArtifactHash = "21edb9cf49eb6e2724852dc090f755cf38564db5026ab4d0b3814f34c0b355e4"
$ExpectedLiveSchema = "id,job_id,source,process_id,pid,process_started_at,status,claimed_at,started_at,finished_at,error,scheduled_at,delivery_outcome,error_class"

$ExpectedInstalledStatus = @(
    " M agent/monitoring/cron_health.py",
    " M cron/executions.py",
    " M cron/jobs.py",
    " M cron/scheduler.py",
    " M gateway/platforms/api_server.py",
    "?? cron/error_classification.py",
    "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
    "?? gateway/platforms/api_server.py.orion-p4-04a.json",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json"
) | Sort-Object

function Stop-P6([string]$Message) {
    throw "STOP: $Message"
}

function Get-KeyValue([string[]]$Output, [string]$Key) {
    $Prefix = $Key + "="
    $Matches = @($Output | Where-Object { $_.StartsWith($Prefix) })
    if ($Matches.Count -ne 1) {
        Stop-P6 "expected exactly one value for $Key."
    }
    return $Matches[0].Substring($Prefix.Length)
}

function Require-Command([string]$Name) {
    $Command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $Command) {
        Stop-P6 "required command not found: $Name"
    }
    Write-Host "P6_UPG_04_COMMAND_$($Name.ToUpperInvariant().Replace('-', '_'))=present"
}

Write-Host "P6_UPG_04_PREFLIGHT_BEGIN=true"
Write-Host "P6_UPG_04_PRODUCTION_MUTATION_AUTHORIZED=false"
Write-Host "P6_UPG_04_GATEWAY_RESTART_AUTHORIZED=false"
Write-Host "P6_UPG_04_LIVE_REMINDER_AUTHORIZED=false"
Write-Host "P6_UPG_04_VENDOR_WARMUP_DISPOSITION=$VendorWarmupDisposition"

if (-not (Test-Path -LiteralPath $OrionRepo -PathType Container)) {
    Stop-P6 "Orion repository missing: $OrionRepo"
}
Set-Location $OrionRepo

$Branch = (git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or $Branch -ne $ExpectedOrionBranch) {
    Stop-P6 "run from $ExpectedOrionBranch; current branch is '$Branch'."
}
if (@(git status --porcelain=v1).Count -ne 0) {
    git status --short
    Stop-P6 "Orion worktree is not clean."
}
Write-Host "P6_UPG_04_ORION_BRANCH=PASS"

$Artifact = Join-Path $OrionRepo "compat\hermes\v2026.9.24-orion-qualified-combined.patch"
$StateProbe = Join-Path $OrionRepo "scripts\phase6\p6-04-production-state-probe.py"
$StateGuard = Join-Path $OrionRepo "scripts\phase6\p6-upg-04-state-guard.py"
foreach ($RequiredFile in @($Artifact, $StateProbe, $StateGuard)) {
    if (-not (Test-Path -LiteralPath $RequiredFile -PathType Leaf)) {
        Stop-P6 "required file missing: $RequiredFile"
    }
}

$ArtifactHash = (Get-FileHash -LiteralPath $Artifact -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "P6_UPG_04_COMBINED_ARTIFACT_SHA256=$ArtifactHash"
if ($ArtifactHash -ne $ExpectedArtifactHash) {
    Stop-P6 "combined compatibility artifact hash drift."
}
Write-Host "P6_UPG_04_COMBINED_ARTIFACT=PASS"

foreach ($Root in @($HermesHome, $CompanionHome, $InstalledHermesRoot)) {
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        Stop-P6 "required production directory missing: $Root"
    }
}

Require-Command "git"
Require-Command "node"
Require-Command "npm"

$ManagedUv = Join-Path $HermesHome "bin\uv.exe"
if (-not (Test-Path -LiteralPath $ManagedUv -PathType Leaf)) {
    $Uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($null -eq $Uv) {
        Stop-P6 "uv is not available from Hermes bin or PATH."
    }
}
Write-Host "P6_UPG_04_UV=present"

$InstalledHermesPython = Join-Path $InstalledHermesRoot "venv\Scripts\python.exe"
$InstalledHermesExe = Join-Path $InstalledHermesRoot "venv\Scripts\hermes.exe"
foreach ($Path in @($InstalledHermesPython, $InstalledHermesExe)) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Stop-P6 "installed Hermes runtime file missing: $Path"
    }
}

$InstalledHead = (git -C $InstalledHermesRoot rev-parse HEAD).Trim()
Write-Host "P6_UPG_04_INSTALLED_HEAD=$InstalledHead"
if ($InstalledHead -ne $ExpectedInstalledHead) {
    Stop-P6 "installed Hermes HEAD drift."
}

$ActualInstalledStatus = @(
    git -C $InstalledHermesRoot status --porcelain=v1 --untracked-files=all |
        ForEach-Object { [string]$_ } |
        Sort-Object
)
$StatusDiff = @(Compare-Object -ReferenceObject $ExpectedInstalledStatus -DifferenceObject $ActualInstalledStatus)
if ($StatusDiff.Count -ne 0) {
    Write-Host "P6_UPG_04_INSTALLED_STATUS_MISMATCH_BEGIN"
    $ActualInstalledStatus | ForEach-Object { Write-Host $_ }
    Write-Host "P6_UPG_04_INSTALLED_STATUS_MISMATCH_END"
    Stop-P6 "installed Hermes dirty set differs from the accepted production set."
}
Write-Host "P6_UPG_04_INSTALLED_SOURCE_BASELINE=PASS"

$ProdState = @(& $InstalledHermesPython -B $StateProbe --companion-home $CompanionHome)
if ($LASTEXITCODE -ne 0) {
    Stop-P6 "production state probe failed."
}
$Jobs = [int](Get-KeyValue $ProdState "P6_04_PROD_STATE_JOB_COUNT")
$Rows = [int](Get-KeyValue $ProdState "P6_04_PROD_STATE_EXECUTION_ROWS")
$Columns = Get-KeyValue $ProdState "P6_04_PROD_STATE_EXECUTION_COLUMNS"
$Mode = Get-KeyValue $ProdState "P6_04_PROD_STATE_SQLITE_MODE"
Write-Host "P6_UPG_04_PRODUCTION_JOB_COUNT=$Jobs"
Write-Host "P6_UPG_04_PRODUCTION_EXECUTION_ROWS=$Rows"
if ($Jobs -ne 0 -or $Rows -ne 0) {
    Stop-P6 "production cron baseline is no longer zero-job/zero-execution."
}
if ($Columns -ne $ExpectedLiveSchema -or $Mode -ne "read_only") {
    Stop-P6 "production cron execution schema or read-only mode drift."
}

$CronGuard = @(& $InstalledHermesPython -B $StateGuard --mode cron --home $CompanionHome)
$CronGuard | ForEach-Object { Write-Host $_ }
if ($LASTEXITCODE -ne 0) {
    Stop-P6 "active cron execution detected or cron guard failed."
}
if ((Get-KeyValue $CronGuard "P6_UPG_04_ACTIVE_EXECUTION_COUNT") -ne "0") {
    Stop-P6 "active cron execution detected."
}
Write-Host "P6_UPG_04_CRON_IDLE=PASS"

$InstallStateRoot = Join-Path $HermesHome "installs"
$PendingMarkers = @()
if (Test-Path -LiteralPath $InstallStateRoot -PathType Container) {
    $PendingMarkers = @(
        Get-ChildItem -LiteralPath $InstallStateRoot -Filter "source-completion-pending" -File -Recurse -ErrorAction SilentlyContinue
    )
}
Write-Host "P6_UPG_04_SOURCE_COMPLETION_PENDING_COUNT=$($PendingMarkers.Count)"
if ($PendingMarkers.Count -ne 0) {
    Stop-P6 "source-completion-pending marker exists; do not upgrade around it."
}

$Listeners = @(Get-NetTCPConnection -LocalPort $GatewayPort -State Listen -ErrorAction SilentlyContinue)
Write-Host "P6_UPG_04_GATEWAY_LISTENER_COUNT=$($Listeners.Count)"
if ($Listeners.Count -ne 1) {
    Stop-P6 "expected exactly one gateway listener on port $GatewayPort."
}

$GatewayPid = [int]$Listeners[0].OwningProcess
$GatewayProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $GatewayPid"
if ($null -eq $GatewayProcess -or -not $GatewayProcess.ExecutablePath) {
    Stop-P6 "could not resolve the gateway process."
}

$GatewayExe = [IO.Path]::GetFullPath([string]$GatewayProcess.ExecutablePath)
$InstalledVenvExe = [IO.Path]::GetFullPath($InstalledHermesPython)
$UsesInstalledVenv = [string]::Equals(
    $GatewayExe, $InstalledVenvExe, [StringComparison]::OrdinalIgnoreCase
)
$LooksLikeGateway = [string]$GatewayProcess.CommandLine -match "(?i)gateway\s+run|hermes_cli\.main.*gateway"
Write-Host "P6_UPG_04_GATEWAY_PID=$GatewayPid"
Write-Host "P6_UPG_04_GATEWAY_EXE_NAME=$([IO.Path]::GetFileName($GatewayExe))"
Write-Host "P6_UPG_04_GATEWAY_USES_INSTALLED_VENV=$($UsesInstalledVenv.ToString().ToLowerInvariant())"
Write-Host "P6_UPG_04_GATEWAY_COMMAND_SHAPE_OK=$($LooksLikeGateway.ToString().ToLowerInvariant())"
if ($UsesInstalledVenv -or -not $LooksLikeGateway) {
    Stop-P6 "gateway topology differs from the accepted Windows production topology."
}
Write-Host "P6_UPG_04_GATEWAY_BASELINE=PASS"

$GatewayStatePath = Join-Path $HermesHome "gateway_state.json"
if (-not (Test-Path -LiteralPath $GatewayStatePath -PathType Leaf)) {
    Stop-P6 "gateway_state.json is missing; cannot prove gateway is idle before upgrade."
}
try {
    $GatewayRuntime = Get-Content -LiteralPath $GatewayStatePath -Raw | ConvertFrom-Json
    $ActiveAgents = [int]($GatewayRuntime.active_agents)
    $ActiveWorkCount = @($GatewayRuntime.active_work | Where-Object { $null -ne $_ }).Count
}
catch {
    Stop-P6 "gateway_state.json could not be parsed for the idle-work gate."
}
Write-Host "P6_UPG_04_GATEWAY_ACTIVE_AGENTS=$ActiveAgents"
Write-Host "P6_UPG_04_GATEWAY_ACTIVE_WORK_COUNT=$ActiveWorkCount"
if ($ActiveAgents -ne 0 -or $ActiveWorkCount -ne 0) {
    Stop-P6 "gateway has active work; defer the upgrade until it is idle."
}
Write-Host "P6_UPG_04_GATEWAY_IDLE=PASS"

$StateDbPaths = @(
    (Join-Path $HermesHome "state.db"),
    (Join-Path $CompanionHome "state.db")
)
$StateDbPresent = 0
foreach ($Db in $StateDbPaths) {
    if (Test-Path -LiteralPath $Db -PathType Leaf) {
        $StateDbPresent += 1
        $Item = Get-Item -LiteralPath $Db
        Write-Host "P6_UPG_04_STATE_DB_PRESENT_$StateDbPresent=true"
        Write-Host "P6_UPG_04_STATE_DB_SIZE_$StateDbPresent=$($Item.Length)"
    }
}
Write-Host "P6_UPG_04_STATE_DB_PRESENT_COUNT=$StateDbPresent"

try {
    $GatewayTasks = @(
        Get-ScheduledTask -ErrorAction Stop |
            Where-Object { $_.TaskName -match "(?i)Hermes.*Gateway|Gateway.*Hermes" }
    )
    Write-Host "P6_UPG_04_GATEWAY_SCHEDULED_TASK_COUNT=$($GatewayTasks.Count)"
    foreach ($Task in $GatewayTasks) {
        Write-Host "P6_UPG_04_GATEWAY_TASK=$($Task.TaskName)|$($Task.State)"
    }
}
catch {
    Write-Host "P6_UPG_04_GATEWAY_SCHEDULED_TASK_COUNT=unavailable"
}

Write-Host "P6_UPG_04_PRODUCTION_READ_ONLY_PREFLIGHT=PASS"

if ($VendorWarmupDisposition -ne "QUALIFIED_FIX_INCLUDED") {
    Write-Host "P6_UPG_04_VENDOR_P1_131145=OPEN_UNRESOLVED"
    Write-Host "P6_UPG_04_VERDICT=NO_GO_VENDOR_P1_WARMUP"
    Write-Host "P6_UPG_04_NEXT=wait_for_vendor_proven_fix_then_requalify_candidate"
    exit 3
}

Write-Host "P6_UPG_04_VENDOR_P1_131145=QUALIFIED_FIX_INCLUDED"
Write-Host "P6_UPG_04_VERDICT=READY_FOR_EXPLICIT_OWNER_AUTHORIZATION"
exit 0
