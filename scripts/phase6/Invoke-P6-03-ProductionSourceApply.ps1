param(
    [Parameter(Mandatory=$true)]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedToken = "I_AUTHORIZE_P6_03_PRODUCTION_SOURCE_APPLY"
$ExpectedBranch = "prep/phase6-p6-02-p6-07"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedPatchBlob = "539651113098298e3f45241636701bd25d7893ef"
$ExpectedPatchedJobsSha256 = "3766fe600b48d28130c4261ec9402bad1969bcc9218ef566610530bd2bdbcfa5"
$PatchRel = "compat/hermes/p6-03-jobs-corruption-preservation.patch"

if ($AuthorizationToken -ne $ExpectedToken) {
    throw "STOP: explicit P6-03 production source-apply authorization is required."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$CompanionCron = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion\cron"
$HermesPython = Join-Path $HermesRoot "venv\Scripts\python.exe"
$Patch = Join-Path $RepoRoot $PatchRel
$Probe = Join-Path $PSScriptRoot "p6-03-disposable-corruption-preservation.py"
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
    throw "STOP: Orion worktree must be clean before P6-03 production source application."
}
if (-not (Test-Path -LiteralPath $Patch)) {
    throw "STOP: qualified P6-03 patch not found: $Patch"
}
if (-not (Test-Path -LiteralPath $Probe)) {
    throw "STOP: P6-03 qualifier not found: $Probe"
}
if (-not (Test-Path -LiteralPath $HermesPython)) {
    throw "STOP: Hermes venv Python not found: $HermesPython"
}
if (-not (Test-Path -LiteralPath $Target)) {
    throw "STOP: installed Hermes target not found: $Target"
}

$PatchBlob = (& git -C $RepoRoot hash-object -- $PatchRel).Trim()
if ($LASTEXITCODE -ne 0 -or $PatchBlob -ne $ExpectedPatchBlob) {
    throw "STOP: qualified patch blob drift. Expected $ExpectedPatchBlob; observed $PatchBlob"
}

$PatchAttr = ((& git -C $RepoRoot check-attr eol -- $PatchRel) -join "")
if ($LASTEXITCODE -ne 0 -or $PatchAttr -notmatch "eol: lf$") {
    throw "STOP: qualified patch must be governed by eol=lf; observed: $PatchAttr"
}

$HermesHeadBefore = (& git -C $HermesRoot rev-parse HEAD).Trim()
if ($HermesHeadBefore -ne $ExpectedHermesHead) {
    throw "STOP: Hermes pin drift. Expected $ExpectedHermesHead; observed $HermesHeadBefore"
}

$ExpectedHermesStatusBefore = @(
    " M gateway/platforms/api_server.py",
    "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
    "?? gateway/platforms/api_server.py.orion-p4-04a.json",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json"
)
$HermesStatusBefore = Get-StatusLines $HermesRoot
Assert-StatusEquals $HermesStatusBefore $ExpectedHermesStatusBefore "pre-apply Hermes"

$HeadTargetBlob = (& git -C $HermesRoot rev-parse "${ExpectedHermesHead}:cron/jobs.py").Trim()
$WorktreeTargetBlob = (& git -C $HermesRoot hash-object -- "cron/jobs.py").Trim()
if ($LASTEXITCODE -ne 0 -or $WorktreeTargetBlob -ne $HeadTargetBlob) {
    throw "STOP: cron/jobs.py already differs from the accepted pinned Git object."
}

$PatchTargets = @(
    Select-String -LiteralPath $Patch -Pattern '^diff --git a/(.+) b/(.+)$' |
        ForEach-Object {
            "{0}|{1}" -f $_.Matches[0].Groups[1].Value, $_.Matches[0].Groups[2].Value
        }
)
if ($PatchTargets.Count -ne 1 -or $PatchTargets[0] -ne "cron/jobs.py|cron/jobs.py") {
    throw "STOP: qualified patch target scope drift: $($PatchTargets -join ', ')"
}

$CompanionBefore = Get-CronMetadata $CompanionCron
$OriginalSha256 = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant()

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $env:LOCALAPPDATA "hermes\orion-compat-backups\p6-03-$Stamp"
$BackupTarget = Join-Path $BackupRoot "cron-jobs.py.original"
$ManifestPath = Join-Path $BackupRoot "manifest.json"
$TempBase = Join-Path $env:TEMP "orion-p6-03-prod-apply-$Stamp"
$NormalizedPatch = Join-Path $TempBase "p6-03-jobs-corruption-preservation.lf.patch"
$DisposableHome = Join-Path $TempBase "hermes-home"

New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
New-Item -ItemType Directory -Path $TempBase -Force | Out-Null
New-Item -ItemType Directory -Path $DisposableHome -Force | Out-Null

[System.IO.File]::WriteAllBytes($BackupTarget, [System.IO.File]::ReadAllBytes($Target))
$BackupSha256 = (Get-FileHash -LiteralPath $BackupTarget -Algorithm SHA256).Hash.ToLowerInvariant()
if ($BackupSha256 -ne $OriginalSha256) {
    throw "STOP: backup hash mismatch before patch application."
}

$Manifest = [ordered]@{
    ticket = "P6-03"
    created_at_local = (Get-Date).ToString("o")
    hermes_head = $HermesHeadBefore
    target = "cron/jobs.py"
    original_sha256 = $OriginalSha256
    qualified_patch_blob = $PatchBlob
    expected_patched_sha256 = $ExpectedPatchedJobsSha256
    orion_head = $RepoHeadBefore
}
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText(
    $ManifestPath,
    ($Manifest | ConvertTo-Json -Depth 4),
    $Utf8NoBom
)

$PatchText = [System.IO.File]::ReadAllText($Patch)
$PatchText = $PatchText.Replace("`r`n", "`n")
if ($PatchText.Contains("`r")) {
    throw "STOP: qualified patch contains a bare CR byte."
}
[System.IO.File]::WriteAllText($NormalizedPatch, $PatchText, $Utf8NoBom)

& git -C $HermesRoot apply --check $NormalizedPatch
if ($LASTEXITCODE -ne 0) {
    throw "STOP: qualified patch no longer applies cleanly immediately before production application."
}

Write-Host "P6_03_PROD_APPLY_REPO_HEAD=$RepoHeadBefore"
Write-Host "P6_03_PROD_APPLY_HERMES_HEAD=$HermesHeadBefore"
Write-Host "P6_03_PROD_APPLY_PATCH_BLOB=$PatchBlob"
Write-Host "P6_03_PROD_APPLY_ORIGINAL_SHA256=$OriginalSha256"
Write-Host "P6_03_PROD_APPLY_BACKUP=$BackupTarget"
Write-Host "P6_03_PROD_APPLY_MANIFEST=$ManifestPath"
Write-Host "P6_03_PROD_APPLY_COMPANION_MUTATION_AUTHORIZED=false"
Write-Host "P6_03_PROD_APPLY_RESTART_AUTHORIZED=false"

$Applied = $false
$Succeeded = $false
$OldDontWriteBytecode = $env:PYTHONDONTWRITEBYTECODE

try {
    & git -C $HermesRoot apply $NormalizedPatch
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: production P6-03 patch application failed."
    }
    $Applied = $true

    $PatchedSha256 = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($PatchedSha256 -ne $ExpectedPatchedJobsSha256) {
        throw "STOP: patched cron/jobs.py SHA-256 mismatch. Expected $ExpectedPatchedJobsSha256; observed $PatchedSha256"
    }
    Write-Host "P6_03_PROD_APPLY_PATCHED_SHA256=$PatchedSha256"

    $ExpectedHermesStatusAfter = @(
        " M cron/jobs.py",
        " M gateway/platforms/api_server.py",
        "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
        "?? gateway/platforms/api_server.py.orion-p4-04a.json",
        "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak",
        "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json"
    )
    $HermesStatusAfterApply = Get-StatusLines $HermesRoot
    Assert-StatusEquals $HermesStatusAfterApply $ExpectedHermesStatusAfter "post-apply Hermes"
    Write-Host "P6_03_PROD_APPLY_CHANGED_SCOPE=cron/jobs.py"

    $CompileOut = Join-Path $TempBase "cron_jobs.pyc"
    & $HermesPython -c "import py_compile,sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)" $Target $CompileOut
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $CompileOut)) {
        throw "STOP: installed patched cron/jobs.py py_compile failed."
    }
    Write-Host "P6_03_PROD_APPLY_PY_COMPILE=PASS"

    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $HermesPython -B $Probe --source-root $HermesRoot --disposable-home $DisposableHome --prepatched
    $ProbeExit = $LASTEXITCODE
    if ($ProbeExit -ne 0) {
        throw "STOP: installed patched source failed full P6-03 disposable qualification."
    }
    Write-Host "P6_03_PROD_APPLY_INSTALLED_SOURCE_QUALIFICATION=PASS"

    $HermesHeadAfter = (& git -C $HermesRoot rev-parse HEAD).Trim()
    if ($HermesHeadAfter -ne $HermesHeadBefore) {
        throw "STOP: Hermes HEAD changed during production source application."
    }

    $RepoHeadAfter = (& git -C $RepoRoot rev-parse HEAD).Trim()
    $RepoStatusAfter = Get-StatusText $RepoRoot
    if ($RepoHeadAfter -ne $RepoHeadBefore -or $RepoStatusAfter -ne $RepoStatusBefore) {
        throw "STOP: Orion repository changed during production source application."
    }

    $CompanionAfter = Get-CronMetadata $CompanionCron
    if (($CompanionAfter -join [Environment]::NewLine) -ne ($CompanionBefore -join [Environment]::NewLine)) {
        throw "STOP: COMPANION cron metadata changed during production source application."
    }

    $FinalStatus = Get-StatusLines $HermesRoot
    Assert-StatusEquals $FinalStatus $ExpectedHermesStatusAfter "final Hermes"

    Write-Host "P6_03_PROD_APPLY_ORION_UNCHANGED=true"
    Write-Host "P6_03_PROD_APPLY_HERMES_HEAD_UNCHANGED=true"
    Write-Host "P6_03_PROD_APPLY_COMPANION_CRON_UNCHANGED=true"
    Write-Host "P6_03_PROD_APPLY_GATEWAY_RESTARTED=false"
    Write-Host "P6_03_PROD_APPLY_LIVE_ACTIVATION=false"
    Write-Host "P6_03_PRODUCTION_SOURCE_APPLICATION=PASS"
    $Succeeded = $true
}
catch {
    Write-Host "P6_03_PROD_APPLY_FAILURE=$($_.Exception.Message)"
    if ($Applied) {
        [System.IO.File]::WriteAllBytes($Target, [System.IO.File]::ReadAllBytes($BackupTarget))
        $RestoredSha256 = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant()
        Write-Host "P6_03_PROD_APPLY_ROLLBACK_SHA256=$RestoredSha256"
        if ($RestoredSha256 -ne $OriginalSha256) {
            throw "STOP: rollback hash mismatch after production apply failure."
        }
        $RollbackStatus = Get-StatusLines $HermesRoot
        Assert-StatusEquals $RollbackStatus $ExpectedHermesStatusBefore "rollback Hermes"
        Write-Host "P6_03_PROD_APPLY_ROLLBACK=PASS"
    }
    Write-Host "P6_03_PROD_APPLY_FAILURE_EVIDENCE=$TempBase"
    throw
}
finally {
    if ($null -eq $OldDontWriteBytecode) {
        Remove-Item Env:PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONDONTWRITEBYTECODE = $OldDontWriteBytecode
    }

    if ($Succeeded -and (Test-Path -LiteralPath $TempBase)) {
        Remove-Item -LiteralPath $TempBase -Recurse -Force
        Write-Host "P6_03_PROD_APPLY_TEMP_ARTIFACTS_REMOVED=true"
    }
}
