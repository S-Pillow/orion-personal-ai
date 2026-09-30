param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("I_AUTHORIZE_P6_02_DISPOSABLE_CRON_ADAPTER")]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# P6-02 qualification mutates only a disposable HERMES_HOME under %TEMP%.
# It does not create or run a COMPANION reminder, start/stop Hermes services,
# edit config, invoke an LLM/provider, or edit the installed Hermes checkout.

$ExpectedBranch = "prep/phase6-p6-02-p6-07"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$HermesPython = Join-Path $HermesRoot "venv\Scripts\python.exe"
$CompanionCron = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion\cron"
$Probe = Join-Path $PSScriptRoot "p6-02-disposable-cron-adapter-qualification.py"

$ExpectedHermesDirty = @(
    " M gateway/platforms/api_server.py",
    "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
    "?? gateway/platforms/api_server.py.orion-p4-04a.json",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak",
    "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json"
) | Sort-Object

function Get-CompanionCronMetadata {
    if (-not (Test-Path -LiteralPath $CompanionCron -PathType Container)) {
        return "<missing>"
    }

    return (@(
        Get-ChildItem -LiteralPath $CompanionCron -Force |
            Sort-Object Name |
            ForEach-Object {
                "{0}|{1}|{2}|{3:o}" -f
                    $_.Name,
                    $(if ($_.PSIsContainer) { "DIR" } else { "FILE" }),
                    $(if ($_.PSIsContainer) { 0 } else { $_.Length }),
                    $_.LastWriteTime
            }
    ) -join [Environment]::NewLine)
}

function Test-GatewayListening {
    try {
        return @(Get-NetTCPConnection -LocalPort 8642 -State Listen -ErrorAction SilentlyContinue).Count -gt 0
    }
    catch {
        return $false
    }
}

if ($AuthorizationToken -ne "I_AUTHORIZE_P6_02_DISPOSABLE_CRON_ADAPTER") {
    throw "STOP: explicit P6-02 disposable qualification authorization required."
}

foreach ($Path in @($HermesRoot, $HermesPython, $Probe)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "STOP: required path missing: $Path"
    }
}

$RepoBranch = (& git -C $Repo branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoBranch -ne $ExpectedBranch) {
    throw "STOP: expected Phase 6 prep branch is not checked out."
}

$RepoStatusBefore = @(& git -C $Repo status --porcelain=v1)
if ($LASTEXITCODE -ne 0 -or $RepoStatusBefore.Count -ne 0) {
    throw "STOP: Orion worktree must be clean."
}

$HermesHeadBefore = (& git -C $HermesRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $HermesHeadBefore -ne $ExpectedHermesHead) {
    throw "STOP: Hermes HEAD differs from accepted runtime."
}

$HermesStatusBefore = @((& git -C $HermesRoot status --porcelain=v1) | Sort-Object)
if (
    $HermesStatusBefore.Count -ne $ExpectedHermesDirty.Count -or
    (Compare-Object $ExpectedHermesDirty $HermesStatusBefore)
) {
    Write-Host "Observed Hermes status:"
    $HermesStatusBefore
    throw "STOP: Hermes worktree differs from accepted compatibility-artifact state."
}

$CompanionBefore = Get-CompanionCronMetadata
$GatewayBefore = Test-GatewayListening

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$DisposableHome = Join-Path $env:TEMP "orion-p6-02-cron-$Stamp"
$Succeeded = $false

Write-Host "P6_02_REPO_BRANCH=$RepoBranch"
Write-Host "P6_02_HERMES_HEAD=$HermesHeadBefore"
Write-Host "P6_02_COMPANION_CRON_METADATA_CAPTURED=true"
Write-Host "P6_02_GATEWAY_LISTENING_BEFORE=$GatewayBefore"
Write-Host "P6_02_DISPOSABLE_HOME=$DisposableHome"
Write-Host "P6_02_COMPANION_MUTATION_AUTHORIZED=false"
Write-Host "P6_02_JOB_RUN_AUTHORIZED=false"

try {
    New-Item -ItemType Directory -Path $DisposableHome -Force | Out-Null

    & $HermesPython $Probe $HermesRoot $DisposableHome
    $ProbeExit = $LASTEXITCODE
    Write-Host "P6_02_PYTHON_EXIT_CODE=$ProbeExit"

    if ($ProbeExit -ne 0) {
        throw "STOP: P6-02 disposable cron adapter probe failed."
    }

    $Succeeded = $true
}
finally {
    $GatewayAfter = Test-GatewayListening
    $CompanionAfter = Get-CompanionCronMetadata
    $HermesHeadAfter = (& git -C $HermesRoot rev-parse HEAD).Trim()
    $HermesStatusAfter = @((& git -C $HermesRoot status --porcelain=v1) | Sort-Object)
    $RepoStatusAfter = @(& git -C $Repo status --porcelain=v1)

    Write-Host "P6_02_GATEWAY_LISTENING_AFTER=$GatewayAfter"
    Write-Host "P6_02_GATEWAY_STATE_UNCHANGED=$($GatewayAfter -eq $GatewayBefore)"
    Write-Host "P6_02_COMPANION_CRON_UNCHANGED=$($CompanionAfter -eq $CompanionBefore)"
    Write-Host "P6_02_HERMES_HEAD_UNCHANGED=$($HermesHeadAfter -eq $HermesHeadBefore)"
    Write-Host "P6_02_HERMES_WORKTREE_UNCHANGED=$(
        $HermesStatusAfter.Count -eq $HermesStatusBefore.Count -and
        -not (Compare-Object $HermesStatusBefore $HermesStatusAfter)
    )"
    Write-Host "P6_02_ORION_WORKTREE_UNCHANGED=$($RepoStatusAfter.Count -eq $RepoStatusBefore.Count)"

    if ($Succeeded) {
        Remove-Item -LiteralPath $DisposableHome -Recurse -Force
        Write-Host "P6_02_DISPOSABLE_HOME_REMOVED=true"
    }
    else {
        Write-Host "P6_02_FAILURE_EVIDENCE_PRESERVED=$DisposableHome"
    }

    if ($GatewayAfter -ne $GatewayBefore) {
        throw "STOP: gateway listener state changed during disposable qualification."
    }
    if ($CompanionAfter -ne $CompanionBefore) {
        throw "STOP: COMPANION cron metadata changed during disposable qualification."
    }
    if ($HermesHeadAfter -ne $HermesHeadBefore) {
        throw "STOP: Hermes HEAD changed during disposable qualification."
    }
    if (
        $HermesStatusAfter.Count -ne $HermesStatusBefore.Count -or
        (Compare-Object $HermesStatusBefore $HermesStatusAfter)
    ) {
        throw "STOP: Hermes worktree changed during disposable qualification."
    }
    if ($RepoStatusAfter.Count -ne $RepoStatusBefore.Count) {
        throw "STOP: Orion worktree changed during disposable qualification."
    }
}

if (-not $Succeeded) {
    throw "STOP: qualification did not complete."
}

Write-Host "P6_02_DISPOSABLE_ADAPTER_QUALIFICATION=PASS"
