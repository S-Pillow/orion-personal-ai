[CmdletBinding()]
param(
    [int]$HermesStopTimeoutSeconds = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$stateRoot = Join-Path $env:LOCALAPPDATA "Orion\operator"
$statePath = Join-Path $stateRoot "launcher-session.json"
$hermesHealthUri = "http://127.0.0.1:8642/health"
$hudHelperPath = Join-Path $PSScriptRoot "Hud-Operator.ps1"
$utf8NoBom = [Text.UTF8Encoding]::new($false)

function Test-DirectHttpEndpoint {
    param(
        [Parameter(Mandatory=$true)][string]$Uri,
        [int]$TimeoutSeconds = 2
    )

    $response = $null
    try {
        $request = [System.Net.HttpWebRequest]::Create($Uri)
        $request.Method = "GET"
        $request.Proxy = $null
        $request.KeepAlive = $false
        $request.AllowAutoRedirect = $false
        $timeoutMs = [Math]::Max(1, $TimeoutSeconds * 1000)
        $request.Timeout = $timeoutMs
        $request.ReadWriteTimeout = $timeoutMs
        $response = [System.Net.HttpWebResponse]$request.GetResponse()
        $statusCode = [int]$response.StatusCode
        return ($statusCode -ge 200 -and $statusCode -lt 300)
    }
    catch {
        return $false
    }
    finally {
        if ($null -ne $response) {
            try { $response.Close() } catch {}
        }
    }
}

function Wait-HermesDown {
    param([int]$TimeoutSeconds = 30)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (-not (Test-DirectHttpEndpoint -Uri $hermesHealthUri)) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    return $false
}

function Read-OrionSessionState {
    if (-not (Test-Path $statePath)) {
        return $null
    }

    try {
        return (Get-Content $statePath -Raw | ConvertFrom-Json)
    }
    catch {
        throw "Orion launcher session state is unreadable: $($_.Exception.Message)"
    }
}

function Write-OrionSessionState {
    param([Parameter(Mandatory=$true)]$State)

    $tmpPath = "$statePath.tmp"
    $json = $State | ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText($tmpPath, $json, $utf8NoBom)
    Move-Item -LiteralPath $tmpPath -Destination $statePath -Force
}

function ConvertTo-OwnedDescendantSnapshot {
    param([Parameter(Mandatory=$true)]$Process)

    return [PSCustomObject]@{
        ProcessId = [int]$Process.ProcessId
        Name = [string]$Process.Name
        ExecutablePath = [string]$Process.ExecutablePath
        CreationDate = [datetime]$Process.CreationDate
    }
}

function Get-PersistedOwnedDescendants {
    param([Parameter(Mandatory=$true)]$SessionState)

    if (-not ($SessionState.PSObject.Properties.Name -contains "ollamaDescendants") -or
        $null -eq $SessionState.ollamaDescendants) {
        return @()
    }

    $snapshots = @()
    foreach ($item in @($SessionState.ollamaDescendants)) {
        foreach ($required in @("ProcessId", "Name", "CreationDate")) {
            if (-not ($item.PSObject.Properties.Name -contains $required) -or
                $null -eq $item.$required -or
                [string]::IsNullOrWhiteSpace([string]$item.$required)) {
                throw "Persisted Orion-owned Ollama descendant state is missing $required."
            }
        }

        $executablePath = $null
        if ($item.PSObject.Properties.Name -contains "ExecutablePath") {
            $executablePath = [string]$item.ExecutablePath
        }

        $snapshots += [PSCustomObject]@{
            ProcessId = [int]$item.ProcessId
            Name = [string]$item.Name
            ExecutablePath = $executablePath
            CreationDate = [datetime]$item.CreationDate
        }
    }

    return @($snapshots)
}

function Merge-OwnedDescendantSnapshots {
    param(
        [Parameter(Mandatory=$true)]
        [AllowEmptyCollection()]
        [object[]]$Existing,

        [Parameter(Mandatory=$true)]
        [AllowEmptyCollection()]
        [object[]]$Fresh
    )

    $byIdentity = [ordered]@{}
    foreach ($snapshot in @($Existing) + @($Fresh)) {
        $creationKey = ([datetime]$snapshot.CreationDate).ToUniversalTime().Ticks
        $key = "$([int]$snapshot.ProcessId)|$creationKey"
        $byIdentity[$key] = $snapshot
    }

    return @($byIdentity.Values)
}

function Save-OwnedDescendantSnapshots {
    param(
        [Parameter(Mandatory=$true)]$SessionState,

        [Parameter(Mandatory=$true)]
        [AllowEmptyCollection()]
        [object[]]$Snapshots
    )

    $persisted = @(
        foreach ($snapshot in @($Snapshots)) {
            [ordered]@{
                ProcessId = [int]$snapshot.ProcessId
                Name = [string]$snapshot.Name
                ExecutablePath = [string]$snapshot.ExecutablePath
                CreationDate = ([datetime]$snapshot.CreationDate).ToString("o")
            }
        }
    )

    $SessionState | Add-Member -NotePropertyName "ollamaDescendants" -NotePropertyValue $persisted -Force
    Write-OrionSessionState -State $SessionState
}

function Get-OrionOwnedDescendantSnapshot {
    param([Parameter(Mandatory=$true)][int]$RootPid)

    $allProcesses = @(Get-CimInstance Win32_Process -ErrorAction Stop)
    $childrenByParent = @{}
    $processByPid = @{}

    foreach ($process in $allProcesses) {
        $processPid = [int]$process.ProcessId
        $processByPid[$processPid] = $process

        $parentPid = [int]$process.ParentProcessId
        if (-not $childrenByParent.ContainsKey($parentPid)) {
            $childrenByParent[$parentPid] = @()
        }
        $childrenByParent[$parentPid] += $process
    }

    if (-not $processByPid.ContainsKey($RootPid)) {
        throw "Orion-owned Ollama root PID $RootPid was not present during descendant snapshot."
    }

    $queue = New-Object 'System.Collections.Generic.Queue[int]'
    $queue.Enqueue($RootPid)
    $seen = @{}
    $snapshots = @()

    while ($queue.Count -gt 0) {
        $parentPid = $queue.Dequeue()
        if (-not $processByPid.ContainsKey($parentPid)) {
            throw "Cannot validate Orion-owned descendant parent PID $parentPid."
        }

        $parentProcess = $processByPid[$parentPid]
        if ($null -eq $parentProcess.CreationDate) {
            throw "Cannot validate creation time for Orion-owned descendant parent PID $parentPid."
        }

        if (-not $childrenByParent.ContainsKey($parentPid)) {
            continue
        }

        foreach ($child in @($childrenByParent[$parentPid])) {
            $childPid = [int]$child.ProcessId
            if ($childPid -le 0 -or $seen.ContainsKey($childPid)) {
                continue
            }

            if ($null -eq $child.CreationDate) {
                throw "Cannot validate creation time for candidate Orion-owned descendant PID $childPid."
            }

            if ([datetime]$child.CreationDate -lt [datetime]$parentProcess.CreationDate) {
                continue
            }

            $seen[$childPid] = $true
            $snapshots += ConvertTo-OwnedDescendantSnapshot -Process $child
            $queue.Enqueue($childPid)
        }
    }

    return @($snapshots)
}

function Get-MatchingSnapshotProcess {
    param([Parameter(Mandatory=$true)]$Snapshot)

    $current = Get-CimInstance Win32_Process -Filter "ProcessId = $($Snapshot.ProcessId)" -ErrorAction Stop
    if ($null -eq $current) {
        return $null
    }

    if ([string]$current.Name -ne [string]$Snapshot.Name) {
        return $null
    }

    if (-not [string]::IsNullOrEmpty([string]$Snapshot.ExecutablePath) -and
        -not [string]::IsNullOrEmpty([string]$current.ExecutablePath) -and
        [string]$current.ExecutablePath -ne [string]$Snapshot.ExecutablePath) {
        return $null
    }

    if ($null -ne $Snapshot.CreationDate -and
        $null -ne $current.CreationDate -and
        [datetime]$current.CreationDate -ne [datetime]$Snapshot.CreationDate) {
        return $null
    }

    return $current
}

function Get-VerifiedSnapshotProcessHandle {
    param([Parameter(Mandatory=$true)]$Snapshot)

    $current = Get-MatchingSnapshotProcess -Snapshot $Snapshot
    if ($null -eq $current) {
        return $null
    }

    $processHandle = $null
    try {
        $processHandle = Get-Process -Id ([int]$Snapshot.ProcessId) -ErrorAction Stop
    }
    catch {
        $recheck = Get-MatchingSnapshotProcess -Snapshot $Snapshot
        if ($null -eq $recheck) {
            return $null
        }
        throw
    }

    $expectedProcessName = [IO.Path]::GetFileNameWithoutExtension([string]$Snapshot.Name)
    if ($processHandle.ProcessName -ne $expectedProcessName) {
        $processHandle.Dispose()
        return $null
    }

    try {
        $startDeltaSeconds = [Math]::Abs(
            ($processHandle.StartTime - [datetime]$Snapshot.CreationDate).TotalSeconds
        )
        if ($startDeltaSeconds -gt 1) {
            $processHandle.Dispose()
            return $null
        }

        if (-not [string]::IsNullOrEmpty([string]$Snapshot.ExecutablePath)) {
            $handlePath = [string]$processHandle.MainModule.FileName
            if ($handlePath -ne [string]$Snapshot.ExecutablePath) {
                $processHandle.Dispose()
                return $null
            }
        }
    }
    catch {
        $processHandle.Dispose()
        throw
    }

    return $processHandle
}

function Stop-OrionOwnedDescendants {
    param(
        [Parameter(Mandatory=$true)]
        [AllowEmptyCollection()]
        [object[]]$Snapshots
    )

    $snapshotsArray = @($Snapshots)
    if ($snapshotsArray.Count -eq 0) {
        return
    }

    $descendantDeadline = (Get-Date).AddSeconds(5)
    do {
        $remainingDescendants = @(
            foreach ($snapshot in $snapshotsArray) {
                if ($null -ne (Get-MatchingSnapshotProcess -Snapshot $snapshot)) {
                    $snapshot
                }
            }
        )

        if ($remainingDescendants.Count -eq 0) {
            Write-Host "Ollama: Orion-owned descendants stopped"
            return
        }

        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $descendantDeadline)

    foreach ($snapshot in $remainingDescendants) {
        $verifiedHandle = Get-VerifiedSnapshotProcessHandle -Snapshot $snapshot
        if ($null -eq $verifiedHandle) {
            continue
        }

        try {
            Write-Host "Ollama: forcing Orion-owned descendant PID $($snapshot.ProcessId) ($($snapshot.Name))"
            $verifiedHandle.Kill()
            [void]$verifiedHandle.WaitForExit(5000)
        }
        finally {
            $verifiedHandle.Dispose()
        }
    }

    $stillRunningDescendants = @(
        foreach ($snapshot in $snapshotsArray) {
            if ($null -ne (Get-MatchingSnapshotProcess -Snapshot $snapshot)) {
                $snapshot
            }
        }
    )

    if ($stillRunningDescendants.Count -gt 0) {
        $remainingIds = ($stillRunningDescendants | ForEach-Object { $_.ProcessId }) -join ","
        throw "Orion-owned Ollama descendant PID(s) still running after stop attempt: $remainingIds"
    }

    Write-Host "Ollama: Orion-owned descendants stopped"
}

try {
    Write-Host "=== STOP ORION ==="

    if (-not (Test-Path -LiteralPath $hudHelperPath)) {
        throw "Installed Orion HUD operator helper is missing: $hudHelperPath"
    }
    . $hudHelperPath

    $hermesCommand = Get-Command "hermes" -CommandType Application -ErrorAction SilentlyContinue
    if ($null -eq $hermesCommand) {
        throw "Hermes executable was not found on PATH."
    }

    Write-Host "Hermes COMPANION: stopping"
    & $hermesCommand.Source -p companion gateway stop
    $stopExitCode = $LASTEXITCODE

    if (-not (Wait-HermesDown -TimeoutSeconds $HermesStopTimeoutSeconds)) {
        throw "Hermes API is still reachable after $HermesStopTimeoutSeconds seconds."
    }

    if ($stopExitCode -ne 0) {
        Write-Host "Hermes stop returned exit code $stopExitCode, but the API is confirmed down."
    }
    else {
        Write-Host "Hermes COMPANION: stopped"
    }

    $sessionState = Read-OrionSessionState
    Stop-OrionOwnedHudBridge -SessionState $sessionState

    if ($null -eq $sessionState) {
        Write-Host "Ollama: not owned by this Orion launcher session; leaving it alone"
    }
    else {
        $ownedDescendants = @(Get-PersistedOwnedDescendants -SessionState $sessionState)
        $hasOwnedParent = (
            $sessionState.PSObject.Properties.Name -contains "ollamaStartedByOrion" -and
            $sessionState.ollamaStartedByOrion -eq $true -and
            $sessionState.PSObject.Properties.Name -contains "ollamaPid" -and
            $null -ne $sessionState.ollamaPid
        )

        if ($hasOwnedParent) {
            $ownedPid = [int]$sessionState.ollamaPid
            $ownedProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $ownedPid" -ErrorAction Stop

            if ($null -ne $ownedProcess -and
                ($ownedProcess.Name -match '^(?i)ollama\.exe$' -or $ownedProcess.ExecutablePath -match '(?i)ollama')) {

                $freshDescendants = @(Get-OrionOwnedDescendantSnapshot -RootPid $ownedPid)
                $ownedDescendants = @(Merge-OwnedDescendantSnapshots -Existing $ownedDescendants -Fresh $freshDescendants)

                Save-OwnedDescendantSnapshots -SessionState $sessionState -Snapshots $ownedDescendants
                if ($ownedDescendants.Count -gt 0) {
                    Write-Host "Ollama: persisted $($ownedDescendants.Count) Orion-owned descendant process identity/identities"
                }

                Write-Host "Ollama: stopping Orion-owned server PID $ownedPid"
                Stop-Process -Id $ownedPid -ErrorAction SilentlyContinue

                $deadline = (Get-Date).AddSeconds(5)
                do {
                    if (-not (Get-Process -Id $ownedPid -ErrorAction SilentlyContinue)) {
                        break
                    }
                    Start-Sleep -Milliseconds 250
                } while ((Get-Date) -lt $deadline)

                if (Get-Process -Id $ownedPid -ErrorAction SilentlyContinue) {
                    Write-Host "Ollama: graceful stop did not exit; forcing Orion-owned PID $ownedPid"
                    Stop-Process -Id $ownedPid -Force -ErrorAction SilentlyContinue
                    Start-Sleep -Milliseconds 500
                }

                if (Get-Process -Id $ownedPid -ErrorAction SilentlyContinue) {
                    throw "Orion-owned Ollama PID $ownedPid is still running after stop attempt."
                }

                Write-Host "Ollama: Orion-owned server stopped"
            }
            elseif ($ownedDescendants.Count -gt 0) {
                Write-Host "Ollama: recorded parent is gone or no longer matches; retrying persisted Orion-owned descendant cleanup"
            }
            else {
                Write-Host "Ollama: recorded Orion-owned PID no longer matches a live Ollama process; leaving other Ollama processes alone"
            }
        }
        elseif ($ownedDescendants.Count -eq 0) {
            Write-Host "Ollama: not owned by this Orion launcher session; leaving it alone"
        }

        Stop-OrionOwnedDescendants -Snapshots $ownedDescendants

        if (Test-Path $statePath) {
            Remove-Item -LiteralPath $statePath -Force
        }
    }

    Write-Host ""
    Write-Host "ORION STOPPED"
    Write-Host "Hermes API: down"
    Write-Host "iai remains under its vendor idle/HIBERNATION lifecycle."
    exit 0
}
catch {
    Write-Host ""
    Write-Host "STOP ORION FAILED"
    Write-Host $_.Exception.Message
    Write-Host "Launcher session state was retained for a safe Stop Orion retry when available."
    exit 1
}
