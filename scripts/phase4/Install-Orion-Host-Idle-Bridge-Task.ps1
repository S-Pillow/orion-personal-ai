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

# Migrate any previous harness-owned bridge only when the PID record proves
# the exact process identity and identifies an Orion host-idle bridge script.
if (Test-Path -LiteralPath $PidPath -PathType Leaf) {
    try {
        $oldRec = (Get-Content -LiteralPath $PidPath -Raw) | ConvertFrom-Json
        $oldPid = [int]$oldRec.pid
        $oldStarted = [DateTimeOffset]::Parse([string]$oldRec.process_started_at)
        $oldProc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
        if ($null -ne $oldProc) {
            $actualStarted = [DateTimeOffset]$oldProc.StartTime.ToUniversalTime()
            $identityMatches = [math]::Abs(($actualStarted - $oldStarted).TotalSeconds) -le 1.0
            $scriptLooksOwned = [string]$oldRec.script_path -match '(?i)Orion.*Host-Idle-Bridge\.ps1$'
            if ($identityMatches -and $scriptLooksOwned) {
                Stop-Process -Id $oldPid -Force -ErrorAction Stop
                $null = $oldProc.WaitForExit(5000)
            }
            elseif ($identityMatches) {
                throw ('Live PID record is not an Orion bridge; refusing to terminate PID {0}.' -f $oldPid)
            }
        }
    }
    catch {
        if ($_.Exception.Message -like 'Live PID record is not an Orion bridge*') {
            throw
        }
    }
}

$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -ne $existingTask) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}

Remove-Item -LiteralPath $OutputPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue

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
