[CmdletBinding()]
param(
    [ValidateSet("SelfTest", "Plan", "Verify", "Apply", "Rollback")]
    [string]$Action = "Verify",
    [string]$Target,
    [string]$HermesPython
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$ExpectedTarget = Join-Path $HermesRoot "gateway\platforms\api_server.py"

function Assert-HermesIdentity {
    param([string]$Mode)

    if (-not (Test-Path -LiteralPath $HermesRoot -PathType Container)) {
        throw "Hermes checkout not found: $HermesRoot"
    }

    $head = (git -C $HermesRoot rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or $head -ne $ExpectedHermesHead) {
        throw "STOP: Hermes HEAD drift. Expected $ExpectedHermesHead, observed $head"
    }

    $p4 = @(
        " M gateway/platforms/api_server.py",
        "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
        "?? gateway/platforms/api_server.py.orion-p4-04a.json"
    ) | Sort-Object

    $p5 = @(
        " M gateway/platforms/api_server.py",
        "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
        "?? gateway/platforms/api_server.py.orion-p4-04a.json",
        "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.bak",
        "?? gateway/platforms/api_server.py.orion-p5-03a2-approval-compat.json"
    ) | Sort-Object

    $actual = @(git -C $HermesRoot status --porcelain=v1) | Sort-Object

    $matchesP4 = (
        $actual.Count -eq $p4.Count -and
        -not (Compare-Object -ReferenceObject $p4 -DifferenceObject $actual)
    )
    $matchesP5 = (
        $actual.Count -eq $p5.Count -and
        -not (Compare-Object -ReferenceObject $p5 -DifferenceObject $actual)
    )

    switch ($Mode) {
        "PreInstall" {
            if (-not $matchesP4) {
                throw "STOP: Hermes worktree is not the exact accepted P4-04A pre-install state."
            }
        }
        "Installed" {
            if (-not $matchesP5) {
                throw "STOP: Hermes worktree is not the exact expected P5-03A2 installed state."
            }
        }
        "Either" {
            if (-not ($matchesP4 -or $matchesP5)) {
                throw "STOP: Hermes worktree matches neither accepted P4-04A nor expected P5-03A2 state."
            }
        }
        default {
            throw "Internal error: unknown Hermes identity mode $Mode"
        }
    }
}


$PatchScript = Join-Path $PSScriptRoot "p5-03a2-session-chat-approval-compat.py"
if (-not (Test-Path -LiteralPath $PatchScript -PathType Leaf)) {
    throw "P5-03A2 patcher not found: $PatchScript"
}

function Test-HermesPythonCandidate {
    param([string]$Candidate)

    if (-not $Candidate -or -not (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
        return $false
    }

    $probe = & $Candidate -c "import importlib.util; s=importlib.util.find_spec('gateway.platforms.api_server'); print('ok' if s and s.origin else '')" 2>$null
    return ($LASTEXITCODE -eq 0 -and (($probe | Select-Object -Last 1) -eq "ok"))
}

function Resolve-HermesPython {
    param([string]$ExplicitPython)

    $candidates = @()
    if ($ExplicitPython) { $candidates += $ExplicitPython }

    $HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
    $candidates += (Join-Path $HermesRoot "venv\Scripts\python.exe")

    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (Test-HermesPythonCandidate -Candidate $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "Could not resolve accepted native Hermes Python."
}

function Test-HermesListening {
    try {
        return (@(Get-NetTCPConnection -LocalPort 8642 -State Listen -ErrorAction SilentlyContinue).Count -gt 0)
    }
    catch {
        return $false
    }
}

$PythonExe = Resolve-HermesPython -ExplicitPython $HermesPython

if ($Action -eq "SelfTest") {
    & $PythonExe $PatchScript --self-test
    exit $LASTEXITCODE
}

if (-not $Target) {
    $resolvedTarget = & $PythonExe -c "import importlib.util, pathlib; s=importlib.util.find_spec('gateway.platforms.api_server'); print(pathlib.Path(s.origin).resolve() if s and s.origin else '')"
    if ($LASTEXITCODE -ne 0 -or -not $resolvedTarget) {
        throw "Could not resolve gateway/platforms/api_server.py from selected Hermes Python."
    }
    $Target = ($resolvedTarget | Select-Object -Last 1).Trim()
}

if (-not (Test-Path -LiteralPath $Target -PathType Leaf)) {
    throw "Hermes API server target not found: $Target"
}

$ResolvedTarget = (Resolve-Path -LiteralPath $Target).Path
$ResolvedExpectedTarget = (Resolve-Path -LiteralPath $ExpectedTarget).Path
if ($ResolvedTarget -ne $ResolvedExpectedTarget) {
    throw "STOP: resolved target is not the accepted Hermes API server file."
}

switch ($Action) {
    "Plan"     { Assert-HermesIdentity -Mode "PreInstall" }
    "Apply"    { Assert-HermesIdentity -Mode "PreInstall" }
    "Rollback" { Assert-HermesIdentity -Mode "Installed" }
    "Verify"   { Assert-HermesIdentity -Mode "Either" }
}

Write-Output "P5-03A2 target: $Target"
Write-Output "Hermes HEAD: $ExpectedHermesHead"
Write-Output "Hermes Python: $PythonExe"

if ($Action -in @("Plan", "Apply", "Rollback") -and (Test-HermesListening)) {
    throw "STOP: Hermes port 8642 is listening. Stop Hermes before $Action."
}

switch ($Action) {
    "Plan" {
        & $PythonExe $PatchScript --target $Target --plan
    }
    "Verify" {
        & $PythonExe $PatchScript --target $Target --verify
    }
    "Apply" {
        & $PythonExe $PatchScript --self-test
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & $PythonExe $PatchScript --target $Target --apply
    }
    "Rollback" {
        & $PythonExe $PatchScript --target $Target --rollback
    }
}

exit $LASTEXITCODE
