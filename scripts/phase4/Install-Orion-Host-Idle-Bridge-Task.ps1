[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BridgeSourcePath,
    [string]$InstalledBridgePath = 'C:\HermesAgent\bin\Orion-Host-Idle-Bridge.ps1',
    [string]$OutputPath = 'C:\HermesAgent\data\orion-runtime\host-idle.json',
    [string]$PidPath = 'C:\HermesAgent\data\orion-runtime\host-idle-bridge.pid',
    [string]$TaskName = 'Orion Host Idle Bridge'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $BridgeSourcePath -PathType Leaf)) {
    throw ('Bridge source missing: {0}' -f $BridgeSourcePath)
}

$installDir = Split-Path -Parent $InstalledBridgePath
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $OutputPath) -Force | Out-Null

Copy-Item -LiteralPath $BridgeSourcePath -Destination $InstalledBridgePath -Force

$powerShellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
if (-not (Test-Path -LiteralPath $powerShellExe -PathType Leaf)) {
    throw ('Windows PowerShell executable missing: {0}' -f $powerShellExe)
}

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$argument = '-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -OutputPath "{1}" -PidPath "{2}" -IntervalSeconds 15' -f `
    $InstalledBridgePath, $OutputPath, $PidPath

$action = New-ScheduledTaskAction -Execute $powerShellExe -Argument $argument
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 10 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew

$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description 'Orion Windows interactive-session idle producer for iai lifecycle compatibility.'

Register-ScheduledTask -TaskName $TaskName -InputObject $task -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Host ('P4_02B1A_TASK_NAME={0}' -f $TaskName)
Write-Host ('P4_02B1A_TASK_USER={0}' -f $currentUser)
Write-Host ('P4_02B1A_TASK_BRIDGE={0}' -f $InstalledBridgePath)
Write-Host 'P4_02B1A_TASK_LOGON_TYPE=Interactive'
Write-Host 'P4_02B1A_TASK_TRIGGER=AtLogOn'
Write-Host 'P4_02B1A_TASK_RESTART_COUNT=10'
Write-Host 'P4_02B1A_HOST_IDLE_TASK_INSTALLED=PASS'
