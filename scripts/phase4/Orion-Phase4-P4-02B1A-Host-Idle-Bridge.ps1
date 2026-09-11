[CmdletBinding()]
param(
    [string]$OutputPath = 'C:\HermesAgent\data\orion-runtime\host-idle.json',
    [string]$PidPath = 'C:\HermesAgent\data\orion-runtime\host-idle-bridge.pid',
    [ValidateRange(5, 300)]
    [int]$IntervalSeconds = 15,
    [string]$ProducerInstanceId = '',
    [ValidateRange(1, 20)]
    [int]$MaxConsecutiveFailures = 3,
    [switch]$Once
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($null -eq ('OrionHostIdle.Native' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

namespace OrionHostIdle
{
    public static class Native
    {
        [StructLayout(LayoutKind.Sequential)]
        private struct LASTINPUTINFO
        {
            public uint cbSize;
            public uint dwTime;
        }

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool GetLastInputInfo(ref LASTINPUTINFO plii);

        public static uint GetIdleMilliseconds()
        {
            LASTINPUTINFO lii = new LASTINPUTINFO();
            lii.cbSize = (uint)Marshal.SizeOf(typeof(LASTINPUTINFO));
            if (!GetLastInputInfo(ref lii))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error());
            }

            uint now = unchecked((uint)Environment.TickCount);
            return unchecked(now - lii.dwTime);
        }
    }
}
'@
}

function Ensure-ParentDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)
    $parent = Split-Path -Parent $Path
    if ([string]::IsNullOrWhiteSpace($parent)) {
        throw ('Path must include a parent directory: {0}' -f $Path)
    }
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}

function Write-AtomicUtf8Json {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Value
    )

    $json = $Value | ConvertTo-Json -Compress
    $nonce = [Guid]::NewGuid().ToString('N')
    $tmp = '{0}.tmp-{1}-{2}' -f $Path, $PID, $nonce
    $backup = '{0}.bak-{1}-{2}' -f $Path, $PID, $nonce
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)

    try {
        [System.IO.File]::WriteAllText($tmp, $json, $utf8NoBom)
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            [System.IO.File]::Replace($tmp, $Path, $backup)
        }
        else {
            [System.IO.File]::Move($tmp, $Path)
        }
    }
    finally {
        if (Test-Path -LiteralPath $tmp -PathType Leaf) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $backup -PathType Leaf) {
            Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        }
    }
}

Ensure-ParentDirectory -Path $OutputPath
Ensure-ParentDirectory -Path $PidPath

if ([string]::IsNullOrWhiteSpace($ProducerInstanceId)) {
    $instanceId = [Guid]::NewGuid().ToString('D')
}
else {
    $parsedInstance = [Guid]::Empty
    if (-not [Guid]::TryParse($ProducerInstanceId, [ref]$parsedInstance)) {
        throw ('ProducerInstanceId is not a valid GUID: {0}' -f $ProducerInstanceId)
    }
    $instanceId = $parsedInstance.ToString('D')
}

$currentProcess = [System.Diagnostics.Process]::GetCurrentProcess()
$producerStartedAt = [DateTimeOffset]$currentProcess.StartTime.ToUniversalTime()
$sequence = [int64]0

$pidPayload = [ordered]@{
    schema_version = 1
    pid = [int]$PID
    producer_instance_id = $instanceId
    process_started_at = $producerStartedAt.ToString('o')
    script_path = $PSCommandPath
}
Write-AtomicUtf8Json -Path $PidPath -Value $pidPayload

function Write-IdleObservation {
    $script:sequence++
    $idleMs = [OrionHostIdle.Native]::GetIdleMilliseconds()
    $idleSec = [math]::Floor(([double]$idleMs) / 1000.0)

    $payload = [ordered]@{
        schema_version = 1
        idle_sec = [int64]$idleSec
        observed_at = [DateTimeOffset]::UtcNow.ToString('o')
        source = 'windows-get-last-input-info'
        producer_instance_id = $instanceId
        producer_pid = [int]$PID
        producer_started_at = $producerStartedAt.ToString('o')
        sequence = [int64]$script:sequence
    }

    Write-AtomicUtf8Json -Path $OutputPath -Value $payload
    return [pscustomobject]$payload
}

Write-Host ('P4_02B1A_HOST_IDLE_BRIDGE_OUTPUT={0}' -f $OutputPath)
Write-Host ('P4_02B1A_HOST_IDLE_BRIDGE_PID_PATH={0}' -f $PidPath)
Write-Host ('P4_02B1A_HOST_IDLE_BRIDGE_INTERVAL_SEC={0}' -f $IntervalSeconds)
Write-Host ('P4_02B1A_HOST_IDLE_BRIDGE_INSTANCE={0}' -f $instanceId)
Write-Host ('P4_02B1A_HOST_IDLE_BRIDGE_PID={0}' -f $PID)
Write-Host ('P4_02B1A_HOST_IDLE_BRIDGE_STARTED_AT={0}' -f $producerStartedAt.ToString('o'))

# Startup is intentionally fail-fast. Task Scheduler owns process restart.
$observation = Write-IdleObservation
Write-Host ('P4_02B1A_HOST_IDLE_BRIDGE_STARTUP_SAMPLE={0}|seq={1}|idle_sec={2}' -f `
    $observation.observed_at, $observation.sequence, $observation.idle_sec)

if ($Once) {
    Write-Host 'P4_02B1A_HOST_IDLE_BRIDGE=PASS'
    exit 0
}

$writeCount = 1
$consecutiveFailures = 0
while ($true) {
    Start-Sleep -Seconds $IntervalSeconds
    try {
        $observation = Write-IdleObservation
        $writeCount++
        $consecutiveFailures = 0

        if (($writeCount % 20) -eq 0) {
            Write-Host ('P4_02B1A_HOST_IDLE_BRIDGE_STATUS={0}|seq={1}|idle_sec={2}' -f `
                $observation.observed_at, $observation.sequence, $observation.idle_sec)
        }
    }
    catch {
        # Do not manufacture activity/idle data. The iai reader fails closed
        # when the last good sample ages past its freshness bound. Persistent
        # producer failure exits nonzero so Task Scheduler can restart it.
        $consecutiveFailures++
        Write-Warning ('host idle observation failed after startup ({0}/{1}): {2}' -f `
            $consecutiveFailures, $MaxConsecutiveFailures, $_.Exception.Message)
        if ($consecutiveFailures -ge $MaxConsecutiveFailures) {
            throw ('host idle producer exceeded consecutive failure limit ({0})' -f $MaxConsecutiveFailures)
        }
    }
}
