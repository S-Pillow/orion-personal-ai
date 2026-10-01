param(
    [Parameter(Mandatory=$true)]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedToken = "I_AUTHORIZE_P6_04_PRODUCTION_PREFLIGHT"
$ExpectedBranch = "prep/phase6-p6-02-p6-07"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedP603JobsSha256 = "3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5"
$ExpectedPatchBlob = "31c1127e032b0a7ea09ecfd92ed3eaa1d5b0542f"
$ExpectedPatchSha256 = "abe54cd59e217f60c01fd8ae68e1cfb1782b7267ff7b98a035b4481f66f787ed"
$PatchRel = "compat/hermes/p6-04-durable-run-evidence.patch"

if ($AuthorizationToken -ne $ExpectedToken) { throw "STOP: explicit P6-04 production preflight authorization is required." }

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$CompanionHome = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion"
$HermesPython = Join-Path $HermesRoot "venv\Scripts\python.exe"
$Patch = Join-Path $RepoRoot $PatchRel
$StateProbe = Join-Path $PSScriptRoot "p6-04-production-state-probe.py"
$P603Target = Join-Path $HermesRoot "cron\jobs.py"
$ExecutionsTarget = Join-Path $HermesRoot "cron\executions.py"
$SchedulerTarget = Join-Path $HermesRoot "cron\scheduler.py"

function Get-StatusLines([string]$Root) { return @(& git -C $Root status --porcelain=v1) }
function Get-StatusText([string]$Root) { return ((Get-StatusLines $Root) -join [Environment]::NewLine) }
function Assert-StatusEquals([string[]]$Actual, [string[]]$Expected, [string]$Label) {
    $ActualSorted = @($Actual | Sort-Object)
    $ExpectedSorted = @($Expected | Sort-Object)
    if (($ActualSorted -join "`n") -ne ($ExpectedSorted -join "`n")) {
        throw "STOP: $Label status mismatch. Actual: $($ActualSorted -join ' || ')"
    }
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
if ($RepoStatusBefore) { throw "STOP: Orion worktree must be clean before P6-04 production preflight." }

foreach ($Required in @($HermesRoot, $HermesPython, $Patch, $StateProbe, $P603Target, $ExecutionsTarget, $SchedulerTarget)) {
    if (-not (Test-Path -LiteralPath $Required)) { throw "STOP: required P6-04 preflight input missing: $Required" }
}

$PatchBlob = (& git -C $RepoRoot hash-object -- $PatchRel).Trim()
if ($LASTEXITCODE -ne 0 -or $PatchBlob -ne $ExpectedPatchBlob) { throw "STOP: qualified P6-04 patch blob drift. Expected $ExpectedPatchBlob; observed $PatchBlob" }
$PatchSha = (Get-FileHash -LiteralPath $Patch -Algorithm SHA256).Hash.ToLowerInvariant()
if ($PatchSha -ne $ExpectedPatchSha256) { throw "STOP: qualified P6-04 patch SHA-256 drift. Expected $ExpectedPatchSha256; observed $PatchSha" }
$PatchAttr = ((& git -C $RepoRoot check-attr eol -- $PatchRel) -join "")
if ($LASTEXITCODE -ne 0 -or $PatchAttr -notmatch "eol: lf$") { throw "STOP: qualified P6-04 patch must be governed by eol=lf; observed: $PatchAttr" }

$HermesHeadBefore = (& git -C $HermesRoot rev-parse HEAD).Trim()
if ($HermesHeadBefore -ne $ExpectedHermesHead) { throw "STOP: Hermes pin drift. Expected $ExpectedHermesHead; observed $HermesHeadBefore" }

$ExpectedHermesStatus = @(
    " M cron/jobs.py",
    " M gateway/platforms/api_server.py",
    "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
    "?? gateway/platforms/api_server.py.orion-p4-04a.json",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json"
)
$HermesStatusBefore = Get-StatusLines $HermesRoot
Assert-StatusEquals $HermesStatusBefore $ExpectedHermesStatus "pre-P6-04 Hermes"

$P603Sha = (Get-FileHash -LiteralPath $P603Target -Algorithm SHA256).Hash.ToLowerInvariant()
if ($P603Sha -ne $ExpectedP603JobsSha256) { throw "STOP: accepted P6-03 cron/jobs.py hash drift." }

foreach ($Rel in @("cron/executions.py", "cron/scheduler.py")) {
    $HeadBlob = (& git -C $HermesRoot rev-parse "${ExpectedHermesHead}:$Rel").Trim()
    $WorktreeBlob = (& git -C $HermesRoot hash-object -- $Rel).Trim()
    if ($LASTEXITCODE -ne 0 -or $WorktreeBlob -ne $HeadBlob) { throw "STOP: $Rel differs from the accepted pinned Git object." }
    & git -C $HermesRoot diff --quiet $ExpectedHermesHead -- $Rel
    if ($LASTEXITCODE -ne 0) { throw "STOP: $Rel has a pre-existing tracked modification." }
}

$PatchTargets = @(
    Select-String -LiteralPath $Patch -Pattern '^diff --git a/(.+) b/(.+)
$StateBefore = Invoke-StateProbe
$StateBefore | ForEach-Object { Write-Host $_ }
$JobCount = [int](Get-ProbeValue $StateBefore "P6_04_PROD_STATE_JOB_COUNT")
$Columns = Get-ProbeValue $StateBefore "P6_04_PROD_STATE_EXECUTION_COLUMNS"
$Rows = [int](Get-ProbeValue $StateBefore "P6_04_PROD_STATE_EXECUTION_ROWS")
$SqliteMode = Get-ProbeValue $StateBefore "P6_04_PROD_STATE_SQLITE_MODE"
if ($JobCount -ne 0) { throw "STOP: COMPANION has $JobCount cron job(s); P6-04 source application preparation is blocked." }
if ($Rows -ne 0) { throw "STOP: COMPANION executions.db contains $Rows row(s); expected discovery baseline is zero." }
if ($SqliteMode -ne "read_only") { throw "STOP: executions.db was not inspected read-only." }
$ExpectedColumns = "id,job_id,source,process_id,pid,process_started_at,status,claimed_at,started_at,finished_at,error"
if ($Columns -ne $ExpectedColumns) { throw "STOP: COMPANION execution schema drift. Observed: $Columns" }

& git -C $HermesRoot apply --check $Patch
if ($LASTEXITCODE -ne 0) { throw "STOP: qualified P6-04 patch does not apply cleanly to installed accepted Hermes source." }

$RepoHeadAfter = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusAfter = Get-StatusText $RepoRoot
$HermesHeadAfter = (& git -C $HermesRoot rev-parse HEAD).Trim()
$HermesStatusAfter = Get-StatusLines $HermesRoot
$StateAfter = Invoke-StateProbe

if ($RepoHeadAfter -ne $RepoHeadBefore -or $RepoStatusAfter -ne $RepoStatusBefore) { throw "STOP: Orion repository changed during P6-04 preflight." }
if ($HermesHeadAfter -ne $HermesHeadBefore) { throw "STOP: Hermes HEAD changed during P6-04 preflight." }
Assert-StatusEquals $HermesStatusAfter $ExpectedHermesStatus "post-preflight Hermes"
if ((Get-ProbeValue $StateAfter "P6_04_PROD_STATE_JOB_COUNT") -ne "0") { throw "STOP: COMPANION job count changed during preflight." }
if ((Get-ProbeValue $StateAfter "P6_04_PROD_STATE_EXECUTION_COLUMNS") -ne $ExpectedColumns) { throw "STOP: COMPANION execution schema changed during preflight." }
if ((Get-ProbeValue $StateAfter "P6_04_PROD_STATE_EXECUTION_ROWS") -ne "0") { throw "STOP: COMPANION execution row count changed during preflight." }

Write-Host "P6_04_PROD_PREFLIGHT_REPO_HEAD=$RepoHeadBefore"
Write-Host "P6_04_PROD_PREFLIGHT_PATCH_BLOB=$PatchBlob"
Write-Host "P6_04_PROD_PREFLIGHT_PATCH_SHA256=$PatchSha"
Write-Host "P6_04_PROD_PREFLIGHT_PATCH_TARGETS=cron/executions.py,cron/scheduler.py"
Write-Host "P6_04_PROD_PREFLIGHT_HERMES_HEAD=$HermesHeadBefore"
Write-Host "P6_04_PROD_PREFLIGHT_P603_JOBS_SHA256=$P603Sha"
Write-Host "P6_04_PROD_PREFLIGHT_GIT_APPLY_CHECK=PASS"
Write-Host "P6_04_PROD_PREFLIGHT_INSTALLED_HERMES_MUTATION=false"
Write-Host "P6_04_PROD_PREFLIGHT_COMPANION_MUTATION=false"
Write-Host "P6_04_PROD_PREFLIGHT_GATEWAY_RESTARTED=false"
Write-Host "P6_04_PRODUCTION_APPLY_PREFLIGHT=PASS"
 |
        ForEach-Object { "{0}|{1}" -f $_.Matches[0].Groups[1].Value, $_.Matches[0].Groups[2].Value }
)
$ExpectedTargets = @("cron/executions.py|cron/executions.py", "cron/scheduler.py|cron/scheduler.py")
$PatchTargetsText = (@($PatchTargets | Sort-Object) -join "`n")
$ExpectedTargetsText = (@($ExpectedTargets | Sort-Object) -join "`n")
if ($PatchTargetsText -ne $ExpectedTargetsText) { throw "STOP: qualified P6-04 patch target scope drift: $($PatchTargets -join ', ')" }

$StateBefore = Invoke-StateProbe
$StateBefore | ForEach-Object { Write-Host $_ }
$JobCount = [int](Get-ProbeValue $StateBefore "P6_04_PROD_STATE_JOB_COUNT")
$Columns = Get-ProbeValue $StateBefore "P6_04_PROD_STATE_EXECUTION_COLUMNS"
$Rows = [int](Get-ProbeValue $StateBefore "P6_04_PROD_STATE_EXECUTION_ROWS")
$SqliteMode = Get-ProbeValue $StateBefore "P6_04_PROD_STATE_SQLITE_MODE"
if ($JobCount -ne 0) { throw "STOP: COMPANION has $JobCount cron job(s); P6-04 source application preparation is blocked." }
if ($Rows -ne 0) { throw "STOP: COMPANION executions.db contains $Rows row(s); expected discovery baseline is zero." }
if ($SqliteMode -ne "read_only") { throw "STOP: executions.db was not inspected read-only." }
$ExpectedColumns = "id,job_id,source,process_id,pid,process_started_at,status,claimed_at,started_at,finished_at,error"
if ($Columns -ne $ExpectedColumns) { throw "STOP: COMPANION execution schema drift. Observed: $Columns" }

& git -C $HermesRoot apply --check $Patch
if ($LASTEXITCODE -ne 0) { throw "STOP: qualified P6-04 patch does not apply cleanly to installed accepted Hermes source." }

$RepoHeadAfter = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusAfter = Get-StatusText $RepoRoot
$HermesHeadAfter = (& git -C $HermesRoot rev-parse HEAD).Trim()
$HermesStatusAfter = Get-StatusLines $HermesRoot
$StateAfter = Invoke-StateProbe

if ($RepoHeadAfter -ne $RepoHeadBefore -or $RepoStatusAfter -ne $RepoStatusBefore) { throw "STOP: Orion repository changed during P6-04 preflight." }
if ($HermesHeadAfter -ne $HermesHeadBefore) { throw "STOP: Hermes HEAD changed during P6-04 preflight." }
Assert-StatusEquals $HermesStatusAfter $ExpectedHermesStatus "post-preflight Hermes"
if ((Get-ProbeValue $StateAfter "P6_04_PROD_STATE_JOB_COUNT") -ne "0") { throw "STOP: COMPANION job count changed during preflight." }
if ((Get-ProbeValue $StateAfter "P6_04_PROD_STATE_EXECUTION_COLUMNS") -ne $ExpectedColumns) { throw "STOP: COMPANION execution schema changed during preflight." }
if ((Get-ProbeValue $StateAfter "P6_04_PROD_STATE_EXECUTION_ROWS") -ne "0") { throw "STOP: COMPANION execution row count changed during preflight." }

Write-Host "P6_04_PROD_PREFLIGHT_REPO_HEAD=$RepoHeadBefore"
Write-Host "P6_04_PROD_PREFLIGHT_PATCH_BLOB=$PatchBlob"
Write-Host "P6_04_PROD_PREFLIGHT_PATCH_SHA256=$PatchSha"
Write-Host "P6_04_PROD_PREFLIGHT_PATCH_TARGETS=cron/executions.py,cron/scheduler.py"
Write-Host "P6_04_PROD_PREFLIGHT_HERMES_HEAD=$HermesHeadBefore"
Write-Host "P6_04_PROD_PREFLIGHT_P603_JOBS_SHA256=$P603Sha"
Write-Host "P6_04_PROD_PREFLIGHT_GIT_APPLY_CHECK=PASS"
Write-Host "P6_04_PROD_PREFLIGHT_INSTALLED_HERMES_MUTATION=false"
Write-Host "P6_04_PROD_PREFLIGHT_COMPANION_MUTATION=false"
Write-Host "P6_04_PROD_PREFLIGHT_GATEWAY_RESTARTED=false"
Write-Host "P6_04_PRODUCTION_APPLY_PREFLIGHT=PASS"
