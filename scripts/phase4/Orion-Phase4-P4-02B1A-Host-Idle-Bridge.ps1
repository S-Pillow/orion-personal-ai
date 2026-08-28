[CmdletBinding()]
param(
    [string]$OutputPath = 'C:\HermesAgent\data\orion-runtime\host-idle.json',
    [ValidateRange(5, 300)]
    [int]$IntervalSeconds = 15,
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

            // GetLastInputInfo.dwTime and Environment.TickCount are both
            // 32-bit tick counters. Unsigned subtraction preserves the
            // correct elapsed interval across the normal wrap boundary.
            uint now = unchecked((uint)Environment.TickCount);
            return unchecked(now - lii.dwTime);
        }
    }
}
'@
}

$parent = Split-Path -Parent $OutputPath
if ([string]::IsNullOrWhiteSpace($parent)) {
    throw 'OutputPath must include a parent directory.'
}
New-Item -ItemType Directory -Path $parent -Force | Out-Null

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-IdleObservation {
    $idleMs = [OrionHostIdle.Native]::GetIdleMilliseconds()
    $idleSec = [math]::Floor(([double]$idleMs) / 1000.0)

    $payload = [ordered]@{
        schema_version = 1
        idle_sec = [int64]$idleSec
        observed_at = [DateTimeOffset]::UtcNow.ToString('o')
        source = 'windows-get-last-input-info'
    }

    $json = $payload | ConvertTo-Json -Compress
    $tmp = '{0}.tmp-{1}-{2}' -f $OutputPath, $PID, ([Guid]::NewGuid().ToString('N'))

    try {
        [System.IO.File]::WriteAllText($tmp, $json, $utf8NoBom)
        if (Test-Path -LiteralPath $OutputPath -PathType Leaf) {
            [System.IO.File]::Replace($tmp, $OutputPath, $null)
        }
        else {
            [System.IO.File]::Move($tmp, $OutputPath)
        }
    }
    finally {
        if (Test-Path -LiteralPath $tmp -PathType Leaf) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
    }

    return $payload
}

Write-Host ('P4_02B1A_HOST_IDLE_BRIDGE_OUTPUT={0}' -f $OutputPath)
Write-Host ('P4_02B1A_HOST_IDLE_BRIDGE_INTERVAL_SEC={0}' -f $IntervalSeconds)

$writeCount = 0
while ($true) {
    try {
        $observation = Write-IdleObservation
        $writeCount++

        if ($writeCount -eq 1 -or ($writeCount % 20) -eq 0) {
            Write-Host ('P4_02B1A_HOST_IDLE_BRIDGE_STATUS={0}|idle_sec={1}' -f $observation.observed_at, $observation.idle_sec)
        }
    }
    catch {
        # Do not manufacture an idle value on failure. The iai-side reader is
        # designed to fail closed once the last valid observation becomes stale.
        Write-Warning ('host idle observation failed: {0}' -f $_.Exception.Message)
    }

    if ($Once) {
        break
    }
    Start-Sleep -Seconds $IntervalSeconds
}

Write-Host 'P4_02B1A_HOST_IDLE_BRIDGE=PASS'
