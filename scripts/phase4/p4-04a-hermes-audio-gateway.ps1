[CmdletBinding()]
param(
    [ValidateSet("SelfTest", "Verify", "Apply", "Rollback")]
    [string]$Action = "Verify",
    [string]$Target,
    [string]$HermesPython
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$PatchScript = Join-Path $PSScriptRoot "p4-04a-hermes-audio-gateway.py"
if (-not (Test-Path -LiteralPath $PatchScript -PathType Leaf)) {
    throw "P4-04A patcher not found: $PatchScript"
}

function Resolve-HermesPython {
    param([string]$ExplicitPython)

    if ($ExplicitPython) {
        $resolved = (Resolve-Path -LiteralPath $ExplicitPython -ErrorAction Stop).Path
        return $resolved
    }

    $hermes = Get-Command hermes -ErrorAction SilentlyContinue
    if ($hermes -and $hermes.Source) {
        $scriptsDir = Split-Path -Parent $hermes.Source
        $venvRoot = Split-Path -Parent $scriptsDir
        $candidate = Join-Path $venvRoot "python.exe"
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python -and $python.Source) {
        return $python.Source
    }

    throw "Could not resolve the Hermes Python interpreter. Pass -HermesPython explicitly."
}

$PythonExe = Resolve-HermesPython -ExplicitPython $HermesPython

if ($Action -eq "SelfTest") {
    & $PythonExe $PatchScript --self-test
    exit $LASTEXITCODE
}

if (-not $Target) {
    $resolvedTarget = & $PythonExe -c "import pathlib; import gateway.platforms.api_server as m; print(pathlib.Path(m.__file__).resolve())"
    if ($LASTEXITCODE -ne 0 -or -not $resolvedTarget) {
        throw "Could not resolve gateway/platforms/api_server.py from the selected Hermes Python."
    }
    $Target = ($resolvedTarget | Select-Object -Last 1).Trim()
}

if (-not (Test-Path -LiteralPath $Target -PathType Leaf)) {
    throw "Hermes API server target not found: $Target"
}

$Target = (Resolve-Path -LiteralPath $Target).Path
Write-Host "P4-04A target: $Target"
Write-Host "Hermes Python: $PythonExe"

if ($Action -in @("Apply", "Rollback")) {
    $listener = Get-NetTCPConnection -LocalPort 8642 -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        throw "Hermes gateway appears to be listening on port 8642. Stop Orion/Hermes before $Action. This wrapper never restarts Hermes automatically."
    }
}

switch ($Action) {
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
