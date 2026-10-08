param(
    [Parameter(Mandatory=$true)]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedToken = "I_AUTHORIZE_P6_03_PRODUCTION_PREFLIGHT"
$ExpectedBranch = "prep/phase6-p6-02-p6-07"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedPatchBlob = "539651113098298e3f45241636701bd25d7893ef"
$PatchRel = "compat/hermes/p6-03-jobs-corruption-preservation.patch"

if ($AuthorizationToken -ne $ExpectedToken) {
    throw "STOP: explicit P6-03 production preflight authorization is required."
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$CompanionCron = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion\cron"
$Patch = Join-Path $RepoRoot $PatchRel

function Get-StatusText([string]$Root) {
    return ((& git -C $Root status --porcelain=v1) -join [Environment]::NewLine)
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

$RepoBranch = (& git -C $RepoRoot branch --show-current).Trim()
$RepoHead = (& git -C $RepoRoot rev-parse HEAD).Trim()
$RepoStatusBefore = Get-StatusText $RepoRoot

if ($RepoBranch -ne $ExpectedBranch) {
    throw "STOP: expected Orion branch $ExpectedBranch; observed $RepoBranch"
}
if ($RepoStatusBefore) {
    throw "STOP: Orion worktree must be clean before P6-03 production preflight."
}
if (-not (Test-Path -LiteralPath $Patch)) {
    throw "STOP: qualified P6-03 patch not found: $Patch"
}

$PatchBlob = (& git -C $RepoRoot hash-object -- $PatchRel).Trim()
if ($LASTEXITCODE -ne 0 -or $PatchBlob -ne $ExpectedPatchBlob) {
    throw "STOP: qualified patch blob drift. Expected $ExpectedPatchBlob; observed $PatchBlob"
}

$PatchAttr = ((& git -C $RepoRoot check-attr eol -- $PatchRel) -join "")
if ($LASTEXITCODE -ne 0 -or $PatchAttr -notmatch "eol: lf$") {
    throw "STOP: qualified patch must be governed by eol=lf; observed: $PatchAttr"
}

if (-not (Test-Path -LiteralPath $HermesRoot)) {
    throw "STOP: installed Hermes root not found: $HermesRoot"
}

$HermesHeadBefore = (& git -C $HermesRoot rev-parse HEAD).Trim()
$HermesStatusBefore = Get-StatusText $HermesRoot
$CompanionBefore = Get-CronMetadata $CompanionCron

if ($HermesHeadBefore -ne $ExpectedHermesHead) {
    throw "STOP: Hermes pin drift. Expected $ExpectedHermesHead; observed $HermesHeadBefore"
}

$ExpectedHermesStatus = @(
    " M gateway/platforms/api_server.py",
    "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
    "?? gateway/platforms/api_server.py.orion-p4-04a.json",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json"
) -join [Environment]::NewLine

if ($HermesStatusBefore -ne $ExpectedHermesStatus) {
    throw "STOP: installed Hermes worktree differs from the accepted pre-P6-03 state."
}

$Target = Join-Path $HermesRoot "cron\jobs.py"
if (-not (Test-Path -LiteralPath $Target)) {
    throw "STOP: installed Hermes target not found: $Target"
}

$HeadTargetBlob = (& git -C $HermesRoot rev-parse "${ExpectedHermesHead}:cron/jobs.py").Trim()
$WorktreeTargetBlob = (& git -C $HermesRoot hash-object -- "cron/jobs.py").Trim()
if ($LASTEXITCODE -ne 0 -or $WorktreeTargetBlob -ne $HeadTargetBlob) {
    throw "STOP: cron/jobs.py already differs from the accepted pinned Git object."
}

& git -C $HermesRoot diff --quiet $ExpectedHermesHead -- "cron/jobs.py"
if ($LASTEXITCODE -ne 0) {
    throw "STOP: cron/jobs.py has a pre-existing tracked modification."
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

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$TempBase = Join-Path $env:TEMP "orion-p6-03-prod-preflight-$Stamp"
$NormalizedPatch = Join-Path $TempBase "p6-03-jobs-corruption-preservation.lf.patch"
New-Item -ItemType Directory -Path $TempBase -Force | Out-Null

try {
    $PatchText = [System.IO.File]::ReadAllText($Patch)
    $PatchText = $PatchText.Replace("`r`n", "`n")
    if ($PatchText.Contains("`r")) {
        throw "STOP: qualified patch contains a bare CR byte."
    }
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($NormalizedPatch, $PatchText, $Utf8NoBom)

    & git -C $HermesRoot apply --check $NormalizedPatch
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: qualified P6-03 patch does not apply cleanly to installed accepted Hermes source."
    }

    $HermesHeadAfter = (& git -C $HermesRoot rev-parse HEAD).Trim()
    $HermesStatusAfter = Get-StatusText $HermesRoot
    $RepoHeadAfter = (& git -C $RepoRoot rev-parse HEAD).Trim()
    $RepoStatusAfter = Get-StatusText $RepoRoot
    $CompanionAfter = Get-CronMetadata $CompanionCron

    if ($HermesHeadAfter -ne $HermesHeadBefore) {
        throw "STOP: Hermes HEAD changed during read-only preflight."
    }
    if ($HermesStatusAfter -ne $HermesStatusBefore) {
        throw "STOP: Hermes worktree changed during read-only preflight."
    }
    if ($RepoHeadAfter -ne $RepoHead -or $RepoStatusAfter -ne $RepoStatusBefore) {
        throw "STOP: Orion repository changed during read-only preflight."
    }
    if (($CompanionAfter -join [Environment]::NewLine) -ne ($CompanionBefore -join [Environment]::NewLine)) {
        throw "STOP: COMPANION cron metadata changed during read-only preflight."
    }

    Write-Host "P6_03_PROD_PREFLIGHT_REPO_BRANCH=$RepoBranch"
    Write-Host "P6_03_PROD_PREFLIGHT_REPO_HEAD=$RepoHead"
    Write-Host "P6_03_PROD_PREFLIGHT_PATCH_BLOB=$PatchBlob"
    Write-Host "P6_03_PROD_PREFLIGHT_PATCH_EOL=lf"
    Write-Host "P6_03_PROD_PREFLIGHT_HERMES_HEAD=$HermesHeadBefore"
    Write-Host "P6_03_PROD_PREFLIGHT_TARGET_BLOB=$WorktreeTargetBlob"
    Write-Host "P6_03_PROD_PREFLIGHT_PATCH_TARGETS=cron/jobs.py"
    Write-Host "P6_03_PROD_PREFLIGHT_GIT_APPLY_CHECK=PASS"
    Write-Host "P6_03_PROD_PREFLIGHT_INSTALLED_HERMES_MUTATION=false"
    Write-Host "P6_03_PROD_PREFLIGHT_COMPANION_MUTATION=false"
    Write-Host "P6_03_PROD_PREFLIGHT_ORION_UNCHANGED=true"
    Write-Host "P6_03_PROD_PREFLIGHT_HERMES_UNCHANGED=true"
    Write-Host "P6_03_PROD_PREFLIGHT_COMPANION_CRON_UNCHANGED=true"
    Write-Host "P6_03_PRODUCTION_APPLY_PREFLIGHT=PASS"
}
finally {
    if (Test-Path -LiteralPath $TempBase) {
        Remove-Item -LiteralPath $TempBase -Recurse -Force
    }
}
