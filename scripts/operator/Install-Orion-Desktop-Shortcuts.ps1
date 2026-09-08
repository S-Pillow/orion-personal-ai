[CmdletBinding()]
param(
    [string]$InstallDirectory = (Join-Path $env:LOCALAPPDATA "Orion\operator")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$sourceStart = Join-Path $PSScriptRoot "Start-Orion.ps1"
$sourceStop = Join-Path $PSScriptRoot "Stop-Orion.ps1"

if (-not (Test-Path $sourceStart)) {
    throw "Missing source file: $sourceStart"
}
if (-not (Test-Path $sourceStop)) {
    throw "Missing source file: $sourceStop"
}

New-Item -ItemType Directory -Path $InstallDirectory -Force | Out-Null

$startDest = Join-Path $InstallDirectory "Start-Orion.ps1"
$stopDest = Join-Path $InstallDirectory "Stop-Orion.ps1"

Copy-Item -LiteralPath $sourceStart -Destination $startDest -Force
Copy-Item -LiteralPath $sourceStop -Destination $stopDest -Force

$desktop = [Environment]::GetFolderPath("Desktop")
$powershell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$shell = New-Object -ComObject WScript.Shell

$startShortcutPath = Join-Path $desktop "Start Orion.lnk"
$startShortcut = $shell.CreateShortcut($startShortcutPath)
$startShortcut.TargetPath = $powershell
$startShortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$startDest`""
$startShortcut.WorkingDirectory = $InstallDirectory
$startShortcut.Description = "Start Orion (Ollama if needed, Hermes COMPANION, then health check)"
$startShortcut.IconLocation = "$powershell,0"
$startShortcut.Save()

$stopShortcutPath = Join-Path $desktop "Stop Orion.lnk"
$stopShortcut = $shell.CreateShortcut($stopShortcutPath)
$stopShortcut.TargetPath = $powershell
$stopShortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$stopDest`""
$stopShortcut.WorkingDirectory = $InstallDirectory
$stopShortcut.Description = "Stop Orion cleanly and release Orion-owned local runtime resources"
$stopShortcut.IconLocation = "$powershell,0"
$stopShortcut.Save()

Write-Host "Installed Orion operator controls:"
Write-Host "  $startDest"
Write-Host "  $stopDest"
Write-Host ""
Write-Host "Desktop shortcuts:"
Write-Host "  $startShortcutPath"
Write-Host "  $stopShortcutPath"
Write-Host ""
Write-Host "No background supervisor was installed."
