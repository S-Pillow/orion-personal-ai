[CmdletBinding()]
param(
    [string]$InstallDirectory = (Join-Path $env:LOCALAPPDATA "Orion\operator")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$sourceStart = Join-Path $PSScriptRoot "Start-Orion.ps1"
$sourceStop = Join-Path $PSScriptRoot "Stop-Orion.ps1"
$sourceHudHelper = Join-Path $PSScriptRoot "Hud-Operator.ps1"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$sourceHudRoot = Join-Path $repoRoot "hud"
$sourceHudBridge = Join-Path $sourceHudRoot "orion_hud_bridge.py"
$sourceHudProjection = Join-Path $sourceHudRoot "action_projection.py"
$sourceHudStatic = Join-Path $sourceHudRoot "static"

foreach ($requiredPath in @(
    $sourceStart,
    $sourceStop,
    $sourceHudHelper,
    $sourceHudBridge,
    $sourceHudProjection,
    (Join-Path $sourceHudStatic "index.html")
)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Missing source file: $requiredPath"
    }
}

New-Item -ItemType Directory -Path $InstallDirectory -Force | Out-Null

$orionRoot = Split-Path -Parent $InstallDirectory
$hudInstallRoot = Join-Path $orionRoot "hud"
$hudStaticDest = Join-Path $hudInstallRoot "static"
New-Item -ItemType Directory -Path $hudStaticDest -Force | Out-Null

$startDest = Join-Path $InstallDirectory "Start-Orion.ps1"
$stopDest = Join-Path $InstallDirectory "Stop-Orion.ps1"
$hudHelperDest = Join-Path $InstallDirectory "Hud-Operator.ps1"
$hudBridgeDest = Join-Path $hudInstallRoot "orion_hud_bridge.py"
$hudProjectionDest = Join-Path $hudInstallRoot "action_projection.py"

Copy-Item -LiteralPath $sourceStart -Destination $startDest -Force
Copy-Item -LiteralPath $sourceStop -Destination $stopDest -Force
Copy-Item -LiteralPath $sourceHudHelper -Destination $hudHelperDest -Force
Copy-Item -LiteralPath $sourceHudBridge -Destination $hudBridgeDest -Force
Copy-Item -LiteralPath $sourceHudProjection -Destination $hudProjectionDest -Force
Copy-Item -Path (Join-Path $sourceHudStatic "*") -Destination $hudStaticDest -Recurse -Force

$desktop = [Environment]::GetFolderPath("Desktop")
$powershell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$shell = New-Object -ComObject WScript.Shell

$startShortcutPath = Join-Path $desktop "Start Orion.lnk"
$startShortcut = $shell.CreateShortcut($startShortcutPath)
$startShortcut.TargetPath = $powershell
$startShortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$startDest`""
$startShortcut.WorkingDirectory = $InstallDirectory
$startShortcut.Description = "Start Orion (local model, Hermes COMPANION, then accepted HUD)"
$startShortcut.IconLocation = "$powershell,0"
$startShortcut.Save()

$stopShortcutPath = Join-Path $desktop "Stop Orion.lnk"
$stopShortcut = $shell.CreateShortcut($stopShortcutPath)
$stopShortcut.TargetPath = $powershell
$stopShortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$stopDest`""
$stopShortcut.WorkingDirectory = $InstallDirectory
$stopShortcut.Description = "Stop Orion cleanly and release Orion-owned HUD/local runtime resources"
$stopShortcut.IconLocation = "$powershell,0"
$stopShortcut.Save()

Write-Host "Installed Orion operator controls:"
Write-Host "  $startDest"
Write-Host "  $stopDest"
Write-Host "  $hudHelperDest"
Write-Host ""
Write-Host "Installed Orion HUD runtime:"
Write-Host "  $hudInstallRoot"
Write-Host ""
Write-Host "Desktop shortcuts:"
Write-Host "  $startShortcutPath"
Write-Host "  $stopShortcutPath"
Write-Host ""
Write-Host "No background supervisor was installed."
