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

function Test-HermesPythonCandidate {
    param([string]$Candidate)

    if (-not $Candidate -or -not (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
        return $false
    }

    try {
        & $Candidate -c "import importlib.util; s=importlib.util.find_spec('gateway.platforms.api_server'); raise SystemExit(0 if s and s.origin else 3)" 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Resolve-HermesPython {
    param([string]$ExplicitPython)

    $candidates = New-Object System.Collections.Generic.List[string]

    if ($ExplicitPython) {
        $resolved = (Resolve-Path -LiteralPath $ExplicitPython -ErrorAction Stop).Path
        $candidates.Add($resolved)
    }

    if ($env:LOCALAPPDATA) {
        $candidates.Add((Join-Path $env:LOCALAPPDATA "hermes\hermes-agent\venv\Scripts\python.exe"))
    }

    $hermesCommands = Get-Command hermes -All -ErrorAction SilentlyContinue
    foreach ($hermes in @($hermesCommands)) {
        if (-not $hermes.Source) { continue }
        $scriptsDir = Split-Path -Parent $hermes.Source
        $venvRoot = Split-Path -Parent $scriptsDir
        $candidates.Add((Join-Path $venvRoot "python.exe"))
    }

    $pythonCommands = Get-Command python -All -ErrorAction SilentlyContinue
    foreach ($python in @($pythonCommands)) {
        if (-not $python.Source) { continue }
        if ($python.Source -match "\\WindowsApps\\python(?:3)?\.exe$") { continue }
        $candidates.Add($python.Source)
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-HermesPythonCandidate -Candidate $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "Could not resolve a Python interpreter that can locate gateway.platforms.api_server. Expected native Hermes candidate: %LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe. Pass -HermesPython explicitly only if the accepted Hermes installation uses a different verified interpreter."
}

$PythonExe = Resolve-HermesPython -ExplicitPython $HermesPython

if ($Action -eq "SelfTest") {
    & $PythonExe $PatchScript --self-test
    exit $LASTEXITCODE
}

if (-not $Target) {
    $resolvedTarget = & $PythonExe -c "import importlib.util, pathlib; s=importlib.util.find_spec('gateway.platforms.api_server'); print(pathlib.Path(s.origin).resolve() if s and s.origin else '')"
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
