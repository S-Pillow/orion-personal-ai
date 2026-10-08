param(
    [Parameter(Mandatory=$true)]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedToken = "I_AUTHORIZE_P6_04_PRODUCTION_SOURCE_APPLY"
$ExpectedBranch = "prep/phase6-p6-02-p6-07"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedP603JobsSha256 = "3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5"
$ExpectedPatchBlob = "31c1127e032b0a7ea09ecfd92ed3eaa1d5b0542f"
$ExpectedPatchSha256 = "abe54cd59e217f60c01fd8ae68e1cfb1782b7267ff7b98a035b4481f66f787ed"
$ExpectedPatchedExecutionsSha256 = "a7a146921af20f97594258f4672c68e0c4955e7c1a1b361e857be8b4e470d208"
$ExpectedPatchedSchedulerSha256 = "6c0a43c175aab8e7d2a0107f6b067bcfa42f9a55650ab8cc761824c37fb02bfe"
$PatchRel = "compat/hermes/p6-04-durable-run-evidence.patch"

if ($AuthorizationToken -ne $ExpectedToken) { throw "STOP: explicit P6-04 production source-apply authorization is required." }

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$CompanionHome = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion"
$HermesPython = Join-Path $HermesRoot "venv\Scripts\python.exe"
$Patch = Join-Path $RepoRoot $PatchRel
$P604Probe = Join-Path $PSScriptRoot "p6-04-disposable-run-evidence-qualification.py"
$P603Probe = Join-Path $PSScriptRoot "p6-03-disposable-corruption-preservation.py"
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
if ($RepoStatusBefore) { throw "STOP: Orion worktree must be clean before P6-04 production source application." }

foreach ($Required in @($HermesRoot, $HermesPython, $Patch, $P604Probe, $P603Probe, $StateProbe, $P603Target, $ExecutionsTarget, $SchedulerTarget)) {
    if (-not (Test-Path -LiteralPath $Required)) { throw "STOP: required P6-04 source-apply input missing: $Required" }
}

$PatchBlob = (& git -C $RepoRoot hash-object -- $PatchRel).Trim()
if ($LASTEXITCODE -ne 0 -or $PatchBlob -ne $ExpectedPatchBlob) { throw "STOP: qualified P6-04 patch blob drift." }
$PatchSha = (Get-FileHash -LiteralPath $Patch -Algorithm SHA256).Hash.ToLowerInvariant()
if ($PatchSha -ne $ExpectedPatchSha256) { throw "STOP: qualified P6-04 patch SHA-256 drift." }
$PatchAttr = ((& git -C $RepoRoot check-attr eol -- $PatchRel) -join "")
if ($LASTEXITCODE -ne 0 -or $PatchAttr -notmatch "eol: lf$") { throw "STOP: qualified P6-04 patch must be governed by eol=lf." }

$HermesHeadBefore = (& git -C $HermesRoot rev-parse HEAD).Trim()
if ($HermesHeadBefore -ne $ExpectedHermesHead) { throw "STOP: Hermes pin drift." }

$ExpectedHermesStatusBefore = @(
    " M cron/jobs.py",
    " M gateway/platforms/api_server.py",
    "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
    "?? gateway/platforms/api_server.py.orion-p4-04a.json",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json"
)
$HermesStatusBefore = Get-StatusLines $HermesRoot
Assert-StatusEquals $HermesStatusBefore $ExpectedHermesStatusBefore "pre-P6-04 Hermes"

$P603Sha = (Get-FileHash -LiteralPath $P603Target -Algorithm SHA256).Hash.ToLowerInvariant()
if ($P603Sha -ne $ExpectedP603JobsSha256) { throw "STOP: accepted P6-03 cron/jobs.py hash drift." }

foreach ($Rel in @("cron/executions.py", "cron/scheduler.py")) {
    $HeadBlob = (& git -C $HermesRoot rev-parse "${ExpectedHermesHead}:$Rel").Trim()
    $WorktreeBlob = (& git -C $HermesRoot hash-object -- $Rel).Trim()
    if ($LASTEXITCODE -ne 0 -or $WorktreeBlob -ne $HeadBlob) { throw "STOP: $Rel differs from the accepted pinned Git object." }
}

$PatchTargets = @(
    Select-String -LiteralPath $Patch -Pattern '^diff --git a/(.+) b/(.+)$' |
        ForEach-Object { "{0}|{1}" -f $_.Matches[0].Groups[1].Value, $_.Matches[0].Groups[2].Value }
)
$ExpectedTargets = @("cron/executions.py|cron/executions.py", "cron/scheduler.py|cron/scheduler.py")
$PatchTargetsText = (@($PatchTargets | Sort-Object) -join "`n")
$ExpectedTargetsText = (@($ExpectedTargets | Sort-Object) -join "`n")
if ($PatchTargetsText -ne $ExpectedTargetsText) { throw "STOP: qualified P6-04 patch target scope drift." }

$StateBefore = Invoke-StateProbe
$JobCountBefore = [int](Get-ProbeValue $StateBefore "P6_04_PROD_STATE_JOB_COUNT")
$ColumnsBefore = Get-ProbeValue $StateBefore "P6_04_PROD_STATE_EXECUTION_COLUMNS"
$RowsBefore = [int](Get-ProbeValue $StateBefore "P6_04_PROD_STATE_EXECUTION_ROWS")
$ModeBefore = Get-ProbeValue $StateBefore "P6_04_PROD_STATE_SQLITE_MODE"
$ExpectedOldColumns = "id,job_id,source,process_id,pid,process_started_at,status,claimed_at,started_at,finished_at,error"
if ($JobCountBefore -ne 0 -or $RowsBefore -ne 0 -or $ModeBefore -ne "read_only" -or $ColumnsBefore -ne $ExpectedOldColumns) { throw "STOP: COMPANION pre-apply state differs from accepted P6-04 baseline." }

$OriginalExecutionsSha = (Get-FileHash -LiteralPath $ExecutionsTarget -Algorithm SHA256).Hash.ToLowerInvariant()
$OriginalSchedulerSha = (Get-FileHash -LiteralPath $SchedulerTarget -Algorithm SHA256).Hash.ToLowerInvariant()

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $env:LOCALAPPDATA "hermes\orion-compat-backups\p6-04-$Stamp"
$BackupExecutions = Join-Path $BackupRoot "cron-executions.py.original"
$BackupScheduler = Join-Path $BackupRoot "cron-scheduler.py.original"
$ManifestPath = Join-Path $BackupRoot "manifest.json"
$TempBase = Join-Path $env:TEMP "orion-p6-04-prod-apply-$Stamp"
$P604Home = Join-Path $TempBase "p6-04-home"
$P603Home = Join-Path $TempBase "p6-03-home"

New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
New-Item -ItemType Directory -Path $TempBase -Force | Out-Null
New-Item -ItemType Directory -Path $P604Home -Force | Out-Null
New-Item -ItemType Directory -Path $P603Home -Force | Out-Null

[System.IO.File]::WriteAllBytes($BackupExecutions, [System.IO.File]::ReadAllBytes($ExecutionsTarget))
[System.IO.File]::WriteAllBytes($BackupScheduler, [System.IO.File]::ReadAllBytes($SchedulerTarget))
$BackupExecutionsSha = (Get-FileHash -LiteralPath $BackupExecutions -Algorithm SHA256).Hash.ToLowerInvariant()
$BackupSchedulerSha = (Get-FileHash -LiteralPath $BackupScheduler -Algorithm SHA256).Hash.ToLowerInvariant()
if ($BackupExecutionsSha -ne $OriginalExecutionsSha -or $BackupSchedulerSha -ne $OriginalSchedulerSha) { throw "STOP: P6-04 backup hash mismatch." }

$Manifest = [ordered]@{
    ticket = "P6-04"
    created_at_local = (Get-Date).ToString("o")
    hermes_head = $HermesHeadBefore
    orion_head = $RepoHeadBefore
    qualified_patch_blob = $PatchBlob
    qualified_patch_sha256 = $PatchSha
    targets = @(
        [ordered]@{ path = "cron/executions.py"; original_sha256 = $OriginalExecutionsSha; expected_patched_sha256 = $ExpectedPatchedExecutionsSha256 },
        [ordered]@{ path = "cron/scheduler.py"; original_sha256 = $OriginalSchedulerSha; expected_patched_sha256 = $ExpectedPatchedSchedulerSha256 }
    )
}
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($ManifestPath, ($Manifest | ConvertTo-Json -Depth 6), $Utf8NoBom)

& git -C $HermesRoot apply --check $Patch
if ($LASTEXITCODE -ne 0) { throw "STOP: qualified P6-04 patch no longer applies cleanly immediately before source application." }

Write-Host "P6_04_PROD_APPLY_REPO_HEAD=$RepoHeadBefore"
Write-Host "P6_04_PROD_APPLY_HERMES_HEAD=$HermesHeadBefore"
Write-Host "P6_04_PROD_APPLY_PATCH_BLOB=$PatchBlob"
Write-Host "P6_04_PROD_APPLY_PATCH_SHA256=$PatchSha"
Write-Host "P6_04_PROD_APPLY_ORIGINAL_EXECUTIONS_SHA256=$OriginalExecutionsSha"
Write-Host "P6_04_PROD_APPLY_ORIGINAL_SCHEDULER_SHA256=$OriginalSchedulerSha"
Write-Host "P6_04_PROD_APPLY_BACKUP_ROOT=$BackupRoot"
Write-Host "P6_04_PROD_APPLY_MANIFEST=$ManifestPath"
Write-Host "P6_04_PROD_APPLY_COMPANION_MUTATION_AUTHORIZED=false"
Write-Host "P6_04_PROD_APPLY_GATEWAY_RESTART_AUTHORIZED=false"

$Applied = $false
$Succeeded = $false
try {
    & git -C $HermesRoot apply $Patch
    if ($LASTEXITCODE -ne 0) { throw "STOP: production P6-04 patch application failed." }
    $Applied = $true

    $PatchedExecutionsSha = (Get-FileHash -LiteralPath $ExecutionsTarget -Algorithm SHA256).Hash.ToLowerInvariant()
    $PatchedSchedulerSha = (Get-FileHash -LiteralPath $SchedulerTarget -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($PatchedExecutionsSha -ne $ExpectedPatchedExecutionsSha256) { throw "STOP: patched cron/executions.py SHA-256 mismatch." }
    if ($PatchedSchedulerSha -ne $ExpectedPatchedSchedulerSha256) { throw "STOP: patched cron/scheduler.py SHA-256 mismatch." }
    Write-Host "P6_04_PROD_APPLY_PATCHED_EXECUTIONS_SHA256=$PatchedExecutionsSha"
    Write-Host "P6_04_PROD_APPLY_PATCHED_SCHEDULER_SHA256=$PatchedSchedulerSha"

    $ExpectedHermesStatusAfter = @(
        " M cron/executions.py",
        " M cron/jobs.py",
        " M cron/scheduler.py",
        " M gateway/platforms/api_server.py",
        "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
        "?? gateway/platforms/api_server.py.orion-p4-04a.json",
        "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak",
        "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json"
    )
    Assert-StatusEquals (Get-StatusLines $HermesRoot) $ExpectedHermesStatusAfter "post-P6-04 apply Hermes"
    Write-Host "P6_04_PROD_APPLY_CHANGED_SCOPE=cron/executions.py,cron/scheduler.py"

    $CompileExecutions = Join-Path $TempBase "cron_executions.pyc"
    $CompileScheduler = Join-Path $TempBase "cron_scheduler.pyc"
    & $HermesPython -c "import py_compile,sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)" $ExecutionsTarget $CompileExecutions
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $CompileExecutions)) { throw "STOP: installed patched cron/executions.py py_compile failed." }
    & $HermesPython -c "import py_compile,sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)" $SchedulerTarget $CompileScheduler
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $CompileScheduler)) { throw "STOP: installed patched cron/scheduler.py py_compile failed." }
    Write-Host "P6_04_PROD_APPLY_PY_COMPILE=PASS"

    & $HermesPython -B $P604Probe --source-root $HermesRoot --disposable-home $P604Home --prepatched
    if ($LASTEXITCODE -ne 0) { throw "STOP: installed P6-04 source failed disposable P6-04 qualification." }
    Write-Host "P6_04_PROD_APPLY_P604_QUALIFICATION=PASS"

    & $HermesPython -B $P603Probe --source-root $HermesRoot --disposable-home $P603Home --prepatched
    if ($LASTEXITCODE -ne 0) { throw "STOP: installed combined source failed P6-03 regression qualification." }
    Write-Host "P6_04_PROD_APPLY_P603_REGRESSION=PASS"

    $StateAfter = Invoke-StateProbe
    if ((Get-ProbeValue $StateAfter "P6_04_PROD_STATE_JOB_COUNT") -ne "0") { throw "STOP: COMPANION job count changed during source application." }
    if ((Get-ProbeValue $StateAfter "P6_04_PROD_STATE_EXECUTION_COLUMNS") -ne $ExpectedOldColumns) { throw "STOP: COMPANION execution schema changed before live activation." }
    if ((Get-ProbeValue $StateAfter "P6_04_PROD_STATE_EXECUTION_ROWS") -ne "0") { throw "STOP: COMPANION execution row count changed during source application." }

    $RepoHeadAfter = (& git -C $RepoRoot rev-parse HEAD).Trim()
    $RepoStatusAfter = Get-StatusText $RepoRoot
    $HermesHeadAfter = (& git -C $HermesRoot rev-parse HEAD).Trim()
    if ($RepoHeadAfter -ne $RepoHeadBefore -or $RepoStatusAfter -ne $RepoStatusBefore) { throw "STOP: Orion repository changed during source application." }
    if ($HermesHeadAfter -ne $HermesHeadBefore) { throw "STOP: Hermes HEAD changed during source application." }
    Assert-StatusEquals (Get-StatusLines $HermesRoot) $ExpectedHermesStatusAfter "final P6-04 Hermes"

    Write-Host "P6_04_PROD_APPLY_ORION_UNCHANGED=true"
    Write-Host "P6_04_PROD_APPLY_HERMES_HEAD_UNCHANGED=true"
    Write-Host "P6_04_PROD_APPLY_COMPANION_SCHEMA_UNCHANGED=true"
    Write-Host "P6_04_PROD_APPLY_GATEWAY_RESTARTED=false"
    Write-Host "P6_04_PROD_APPLY_LIVE_ACTIVATION=false"
    Write-Host "P6_04_PRODUCTION_SOURCE_APPLICATION=PASS"
    $Succeeded = $true
}
catch {
    Write-Host "P6_04_PROD_APPLY_FAILURE=$($_.Exception.Message)"
    if ($Applied) {
        [System.IO.File]::WriteAllBytes($ExecutionsTarget, [System.IO.File]::ReadAllBytes($BackupExecutions))
        [System.IO.File]::WriteAllBytes($SchedulerTarget, [System.IO.File]::ReadAllBytes($BackupScheduler))
        $RestoredExecutionsSha = (Get-FileHash -LiteralPath $ExecutionsTarget -Algorithm SHA256).Hash.ToLowerInvariant()
        $RestoredSchedulerSha = (Get-FileHash -LiteralPath $SchedulerTarget -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($RestoredExecutionsSha -ne $OriginalExecutionsSha -or $RestoredSchedulerSha -ne $OriginalSchedulerSha) { throw "STOP: rollback hash mismatch after P6-04 source-apply failure." }
        Assert-StatusEquals (Get-StatusLines $HermesRoot) $ExpectedHermesStatusBefore "rollback P6-04 Hermes"
        Write-Host "P6_04_PROD_APPLY_ROLLBACK=PASS"
    }
    Write-Host "P6_04_PROD_APPLY_FAILURE_EVIDENCE=$TempBase"
    throw
}
finally {
    if ($Succeeded -and (Test-Path -LiteralPath $TempBase)) {
        Remove-Item -LiteralPath $TempBase -Recurse -Force
        Write-Host "P6_04_PROD_APPLY_TEMP_ARTIFACTS_REMOVED=true"
    }
}
