param(
    [string]$OrionRepo = "D:\Orion\orion-personal-ai",
    [string]$Python = "C:\Users\spill\AppData\Local\Programs\Python\Python311\python.exe"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedBranch = "feature/p6-upg-04-controlled-production-upgrade"
$ExpectedArtifactHash = "21edb9cf49eb6e2724852dc090f755cf38564db5026ab4d0b3814f34c0b355e4"
$ExpectedInstallerHash = "0a80dfeb7434229933bac32e73140d10086dff81bd84b156e71be9abc87cddf2"

function Stop-P6([string]$Message) {
    throw "STOP: $Message"
}

Set-Location $OrionRepo

$Branch = (git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or $Branch -ne $ExpectedBranch) {
    Stop-P6 "packet self-check must run from $ExpectedBranch."
}

$PowerShellFiles = @(
    "scripts\phase6\Invoke-P6-UPG-04-Preflight.ps1",
    "scripts\phase6\Invoke-P6-UPG-04-ControlledUpgrade.ps1"
)

foreach ($Relative in $PowerShellFiles) {
    $Path = (Resolve-Path (Join-Path $OrionRepo $Relative)).Path
    $Tokens = $null
    $Errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        $Path,
        [ref]$Tokens,
        [ref]$Errors
    )
    if ($Errors.Count -ne 0) {
        $Errors | ForEach-Object { Write-Host "$Relative :: $($_.Message)" }
        Stop-P6 "PowerShell parser errors in $Relative"
    }
    Write-Host "P6_UPG_04_PS_PARSE_PASS=$Relative"
}

$PythonGuard = Join-Path $OrionRepo "scripts\phase6\p6-upg-04-state-guard.py"
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    Stop-P6 "Python interpreter missing: $Python"
}
& $Python -B -c "import pathlib,sys; p=pathlib.Path(sys.argv[1]); compile(p.read_text(encoding='utf-8-sig'), str(p), 'exec'); print('P6_UPG_04_PY_PARSE_PASS=' + str(p))" $PythonGuard
if ($LASTEXITCODE -ne 0) {
    Stop-P6 "Python state guard parse failed."
}

$Artifact = Join-Path $OrionRepo "compat\hermes\v2026.9.24-orion-qualified-combined.patch"
$Hash = (Get-FileHash -LiteralPath $Artifact -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "P6_UPG_04_PACKET_ARTIFACT_SHA256=$Hash"
if ($Hash -ne $ExpectedArtifactHash) {
    Stop-P6 "combined compatibility artifact hash mismatch."
}

$Controlled = Join-Path $OrionRepo "scripts\phase6\Invoke-P6-UPG-04-ControlledUpgrade.ps1"
$ControlledText = Get-Content -LiteralPath $Controlled -Raw
foreach ($RequiredText in @(
    'P6-UPG-04-PRODUCTION-UPGRADE',
    'p6-upg-04-warmup-clearance.json',
    'qualified_fix_included',
    'upstream_merged_commit',
    'stable_release',
    'Invoke-P6Rollback',
    'sqlite-backup',
    'Get-StateDbPaths',
    'P6_UPG_04_GATEWAY_IDLE=PASS',
    'P6_UPG_04_PRESTOP_IDLE_RECHECK=PASS',
    'P6_UPG_04_STATE_SAFETY_HOLD=true',
    'AllowEmergencyForceStop',
    'P6_UPG_04_ROLLBACK_BLOCKED_LIVE_LISTENER=true',
    'v2026.9.24-orion-qualified-combined.patch',
    'HERMES_UPDATE_COMMAND_USED=false',
    $ExpectedInstallerHash
)) {
    if (-not $ControlledText.Contains($RequiredText)) {
        Stop-P6 "controlled-upgrade guard text missing: $RequiredText"
    }
}
if ($ControlledText -match '(?im)&\s*hermes(?:\.exe)?\s+update\b') {
    Stop-P6 "controlled packet unexpectedly invokes hermes update."
}

$ForceStopMatches = @([regex]::Matches($ControlledText, '(?im)^\s*Stop-Process\b.*-Force\b'))
if ($ForceStopMatches.Count -gt 1) {
    Stop-P6 "controlled packet contains more than one force-stop site."
}
if ($ForceStopMatches.Count -eq 1) {
    $GuardIndex = $ControlledText.IndexOf('if (-not $AllowEmergencyForceStop)')
    $ForceIndex = $ControlledText.IndexOf($ForceStopMatches[0].Value)
    if ($GuardIndex -lt 0 -or $GuardIndex -gt $ForceIndex) {
        Stop-P6 "force-stop site is not behind the explicit emergency authorization guard."
    }
}
Write-Host "P6_UPG_04_EMERGENCY_FORCE_STOP_STATIC_GUARD=PASS"
Write-Host "P6_UPG_04_STATIC_GUARD_REVIEW=PASS"

$Preview = @(
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Controlled 2>&1
)
if ($LASTEXITCODE -ne 0) {
    $Preview | ForEach-Object { Write-Host $_ }
    Stop-P6 "controlled-upgrade no-execute preview returned nonzero."
}
if (-not ($Preview -contains "P6_UPG_04_RESULT=NO_MUTATION_PREVIEW_ONLY")) {
    $Preview | ForEach-Object { Write-Host $_ }
    Stop-P6 "controlled-upgrade preview did not prove no-mutation mode."
}
Write-Host "P6_UPG_04_NO_MUTATION_PREVIEW=PASS"

$Clearance = Join-Path $OrionRepo "docs\phase6\p6-upg-04-warmup-clearance.json"
Write-Host "P6_UPG_04_WARMUP_CLEARANCE_PRESENT=$((Test-Path -LiteralPath $Clearance -PathType Leaf).ToString().ToLowerInvariant())"

if (@(git status --porcelain=v1).Count -ne 0) {
    git status --short
    Stop-P6 "packet self-check changed or found a dirty Orion worktree."
}

Write-Host "P6_UPG_04_PACKET_SELF_CHECK=PASS"
