Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:OrionHudUrl = "http://127.0.0.1:8765/"
$script:OrionHudPort = 8765
$script:OrionHudServerPrefix = "OrionHUD/2A"
$script:OrionHudTitleMarker = "<title>Orion // Personal AI Companion</title>"

function Test-OrionHudEndpoint {
    param(
        [string]$Uri = $script:OrionHudUrl,
        [int]$TimeoutSeconds = 2
    )

    $response = $null
    $reader = $null
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

        if ([int]$response.StatusCode -ne 200) {
            return $false
        }

        $serverHeader = [string]$response.Headers["Server"]
        if (-not $serverHeader.StartsWith(
            $script:OrionHudServerPrefix,
            [StringComparison]::OrdinalIgnoreCase
        )) {
            return $false
        }

        $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
        $body = $reader.ReadToEnd()
        return $body.Contains($script:OrionHudTitleMarker)
    }
    catch {
        return $false
    }
    finally {
        if ($null -ne $reader) {
            try { $reader.Dispose() } catch {}
        }
        if ($null -ne $response) {
            try { $response.Close() } catch {}
        }
    }
}

function Wait-OrionHudEndpoint {
    param(
        [string]$Uri = $script:OrionHudUrl,
        [int]$TimeoutSeconds = 15
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (Test-OrionHudEndpoint -Uri $Uri) {
            return $true
        }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)

    return $false
}

function Get-OrionHudListenerPid {
    try {
        $listeners = @(
            Get-NetTCPConnection `
                -LocalPort $script:OrionHudPort `
                -State Listen `
                -ErrorAction SilentlyContinue
        )
        if ($listeners.Count -gt 0) {
            return [int]$listeners[0].OwningProcess
        }
    }
    catch {}

    return $null
}

function Resolve-OrionHudPython {
    $python = Get-Command "python.exe" -CommandType Application -ErrorAction SilentlyContinue
    if ($null -eq $python) {
        $python = Get-Command "python" -CommandType Application -ErrorAction SilentlyContinue
    }
    if ($null -eq $python) {
        throw "Python 3.11+ was not found on PATH for the Orion HUD bridge."
    }

    $probeCode = "import json, os, sys; base=getattr(sys, '_base_executable', None) or sys.executable; print(json.dumps({'major':sys.version_info.major,'minor':sys.version_info.minor,'base_executable':os.path.realpath(base)}))"
    try {
        $probeJson = & $python.Source -c $probeCode 2>$null
    }
    catch {
        throw "Unable to inspect the Python runtime for the Orion HUD bridge."
    }

    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$probeJson)) {
        throw "Unable to inspect the Python runtime for the Orion HUD bridge."
    }

    try {
        $probe = ([string]$probeJson).Trim() | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "Python runtime inspection returned invalid metadata."
    }

    if ([int]$probe.major -ne 3 -or [int]$probe.minor -lt 11) {
        throw "Orion HUD requires Python 3.11+; detected $($probe.major).$($probe.minor)."
    }
    if ([string]::IsNullOrWhiteSpace([string]$probe.base_executable)) {
        throw "Python runtime inspection did not identify a base interpreter."
    }

    try {
        $basePython = (Resolve-Path -LiteralPath ([string]$probe.base_executable) -ErrorAction Stop).Path
    }
    catch {
        throw "Python base interpreter does not exist: $($probe.base_executable)"
    }

    # Launch the real base interpreter, not a possible Windows virtualenv redirector.
    try {
        $baseVersionText = & $basePython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    }
    catch {
        throw "Unable to validate the resolved Python base interpreter."
    }
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$baseVersionText)) {
        throw "Unable to validate the resolved Python base interpreter."
    }

    $baseParts = ([string]$baseVersionText).Trim().Split('.')
    if ($baseParts.Count -lt 2 -or [int]$baseParts[0] -ne 3 -or [int]$baseParts[1] -lt 11) {
        throw "Resolved Orion HUD Python must be 3.11+; detected $(([string]$baseVersionText).Trim())."
    }

    return $basePython
}

function Test-OrionHudIdentityFieldsPresent {
    param([Parameter(Mandatory=$true)]$SessionState)

    foreach ($name in @(
        "hudPid",
        "hudProcessName",
        "hudExecutablePath",
        "hudCreationDate",
        "hudBridgePath"
    )) {
        if (-not ($SessionState.PSObject.Properties.Name -contains $name) -or
            $null -eq $SessionState.$name -or
            [string]::IsNullOrWhiteSpace([string]$SessionState.$name)) {
            return $false
        }
    }

    return $true
}

function Get-OrionHudMatchingProcess {
    param([Parameter(Mandatory=$true)]$SessionState)

    if (-not ($SessionState.PSObject.Properties.Name -contains "hudStartedByOrion") -or
        $SessionState.hudStartedByOrion -ne $true) {
        return $null
    }

    if (-not (Test-OrionHudIdentityFieldsPresent -SessionState $SessionState)) {
        throw "Persisted Orion-owned HUD state is incomplete; refusing unsafe process cleanup."
    }

    $pidValue = [int]$SessionState.hudPid
    $current = Get-CimInstance Win32_Process -Filter "ProcessId = $pidValue" -ErrorAction Stop
    if ($null -eq $current) {
        return $null
    }

    if ([string]$current.Name -ne [string]$SessionState.hudProcessName) {
        return $null
    }

    if ([string]::IsNullOrWhiteSpace([string]$current.ExecutablePath)) {
        throw "Cannot verify executable path for recorded Orion-owned HUD PID $pidValue."
    }
    if (-not [string]::Equals(
        [string]$current.ExecutablePath,
        [string]$SessionState.hudExecutablePath,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        return $null
    }

    if ($null -eq $current.CreationDate) {
        throw "Cannot verify creation time for recorded Orion-owned HUD PID $pidValue."
    }
    $creationDelta = [Math]::Abs(
        (
            [datetime]$current.CreationDate -
            [datetime]$SessionState.hudCreationDate
        ).TotalSeconds
    )
    if ($creationDelta -gt 1) {
        return $null
    }

    if ([string]::IsNullOrWhiteSpace([string]$current.CommandLine)) {
        throw "Cannot verify command line for recorded Orion-owned HUD PID $pidValue."
    }
    if ($current.CommandLine.IndexOf(
        [string]$SessionState.hudBridgePath,
        [StringComparison]::OrdinalIgnoreCase
    ) -lt 0) {
        return $null
    }

    return $current
}

function Get-OrionHudVerifiedProcessHandle {
    param([Parameter(Mandatory=$true)]$SessionState)

    $current = Get-OrionHudMatchingProcess -SessionState $SessionState
    if ($null -eq $current) {
        return $null
    }

    $handle = $null
    try {
        $handle = Get-Process -Id ([int]$SessionState.hudPid) -ErrorAction Stop
    }
    catch {
        $recheck = Get-OrionHudMatchingProcess -SessionState $SessionState
        if ($null -eq $recheck) {
            return $null
        }
        throw
    }

    $expectedName = [IO.Path]::GetFileNameWithoutExtension([string]$SessionState.hudProcessName)
    if ($handle.ProcessName -ne $expectedName) {
        $handle.Dispose()
        return $null
    }

    try {
        $startDelta = [Math]::Abs(
            (
                $handle.StartTime -
                [datetime]$SessionState.hudCreationDate
            ).TotalSeconds
        )
        if ($startDelta -gt 1) {
            $handle.Dispose()
            return $null
        }

        $handlePath = [string]$handle.MainModule.FileName
        if (-not [string]::Equals(
            $handlePath,
            [string]$SessionState.hudExecutablePath,
            [StringComparison]::OrdinalIgnoreCase
        )) {
            $handle.Dispose()
            return $null
        }
    }
    catch {
        $handle.Dispose()
        throw
    }

    return $handle
}

function New-OrionHudResult {
    param(
        [Parameter(Mandatory=$true)][bool]$StartedByOrion,
        $ProcessId = $null,
        $ProcessName = $null,
        $ExecutablePath = $null,
        $CreationDate = $null,
        [Parameter(Mandatory=$true)][string]$BridgePath,
        [string]$StdoutPath = "",
        [string]$StderrPath = ""
    )

    return [PSCustomObject]@{
        StartedByOrion = $StartedByOrion
        ProcessId = $ProcessId
        ProcessName = $ProcessName
        ExecutablePath = $ExecutablePath
        CreationDate = $CreationDate
        BridgePath = $BridgePath
        Url = $script:OrionHudUrl
        StdoutPath = $StdoutPath
        StderrPath = $StderrPath
    }
}

function Start-OrionHudBridge {
    param(
        [Parameter(Mandatory=$true)][string]$HudRoot,
        [Parameter(Mandatory=$true)][string]$LogRoot,
        $PriorState = $null,
        [int]$TimeoutSeconds = 15
    )

    $bridgePath = Join-Path $HudRoot "orion_hud_bridge.py"
    $projectionPath = Join-Path $HudRoot "action_projection.py"
    $indexPath = Join-Path $HudRoot "static\index.html"

    foreach ($requiredPath in @($bridgePath, $projectionPath, $indexPath)) {
        if (-not (Test-Path -LiteralPath $requiredPath)) {
            throw "Installed Orion HUD runtime is incomplete: $requiredPath"
        }
    }

    if (Test-OrionHudEndpoint) {
        if ($null -ne $PriorState -and
            $PriorState.PSObject.Properties.Name -contains "hudStartedByOrion" -and
            $PriorState.hudStartedByOrion -eq $true) {

            $ownedCurrent = Get-OrionHudMatchingProcess -SessionState $PriorState
            if ($null -ne $ownedCurrent) {
                Write-Host "HUD bridge: already available (Orion-owned PID $($PriorState.hudPid))"
                return New-OrionHudResult `
                    -StartedByOrion $true `
                    -ProcessId ([int]$PriorState.hudPid) `
                    -ProcessName ([string]$PriorState.hudProcessName) `
                    -ExecutablePath ([string]$PriorState.hudExecutablePath) `
                    -CreationDate ([datetime]$PriorState.hudCreationDate) `
                    -BridgePath ([string]$PriorState.hudBridgePath)
            }
        }

        Write-Host "HUD bridge: already available (pre-existing; ownership not claimed)"
        return New-OrionHudResult -StartedByOrion $false -BridgePath $bridgePath
    }

    if ($null -ne $PriorState -and
        $PriorState.PSObject.Properties.Name -contains "hudStartedByOrion" -and
        $PriorState.hudStartedByOrion -eq $true) {

        $ownedButUnhealthy = Get-OrionHudMatchingProcess -SessionState $PriorState
        if ($null -ne $ownedButUnhealthy) {
            throw "Recorded Orion-owned HUD PID $($PriorState.hudPid) is still running but the HUD endpoint is unhealthy. Run Stop Orion before retrying Start Orion."
        }
    }

    $listenerPid = Get-OrionHudListenerPid
    if ($null -ne $listenerPid) {
        throw "Port $script:OrionHudPort is occupied by unverified PID $listenerPid; refusing to replace or claim it as the Orion HUD."
    }

    $pythonExe = Resolve-OrionHudPython
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $stdoutPath = Join-Path $LogRoot "hud-$stamp.stdout.log"
    $stderrPath = Join-Path $LogRoot "hud-$stamp.stderr.log"
    $arguments = @(
        "`"$bridgePath`"",
        "--host", "127.0.0.1",
        "--port", "$script:OrionHudPort",
        "--hermes-url", "http://127.0.0.1:8642"
    )

    Write-Host "HUD bridge: starting"
    $process = Start-Process `
        -FilePath $pythonExe `
        -ArgumentList $arguments `
        -WorkingDirectory $HudRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -PassThru

    try {
        $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
        do {
            $process.Refresh()
            if ($process.HasExited) {
                throw "Orion HUD bridge exited before becoming healthy (exit code $($process.ExitCode)). Logs: $stdoutPath ; $stderrPath"
            }
            if (Test-OrionHudEndpoint) {
                break
            }
            Start-Sleep -Milliseconds 250
        } while ((Get-Date) -lt $deadline)

        if (-not (Test-OrionHudEndpoint)) {
            $boundPid = Get-OrionHudListenerPid
            if ($null -ne $boundPid) {
                throw "Orion HUD bridge bound port $script:OrionHudPort but failed identity/readiness checks. Listener PID: $boundPid. Logs: $stdoutPath ; $stderrPath"
            }
            throw "Orion HUD bridge did not become healthy within $TimeoutSeconds seconds. Logs: $stdoutPath ; $stderrPath"
        }

        $current = Get-CimInstance Win32_Process -Filter "ProcessId = $($process.Id)" -ErrorAction Stop
        if ($null -eq $current) {
            throw "Started Orion HUD PID $($process.Id) disappeared before ownership could be recorded."
        }
        if ([string]::IsNullOrWhiteSpace([string]$current.ExecutablePath) -or
            [string]::IsNullOrWhiteSpace([string]$current.CommandLine) -or
            $null -eq $current.CreationDate) {
            throw "Unable to capture a complete identity for started Orion HUD PID $($process.Id)."
        }
        if ($current.CommandLine.IndexOf(
            $bridgePath,
            [StringComparison]::OrdinalIgnoreCase
        ) -lt 0) {
            throw "Started HUD PID $($process.Id) does not identify the installed Orion HUD bridge."
        }

        Write-Host "HUD bridge: ready (PID $($process.Id))"
        return New-OrionHudResult `
            -StartedByOrion $true `
            -ProcessId ([int]$process.Id) `
            -ProcessName ([string]$current.Name) `
            -ExecutablePath ([string]$current.ExecutablePath) `
            -CreationDate ([datetime]$current.CreationDate) `
            -BridgePath $bridgePath `
            -StdoutPath $stdoutPath `
            -StderrPath $stderrPath
    }
    catch {
        if (-not $process.HasExited) {
            try {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
            catch {}
        }
        throw
    }
}

function Open-OrionHud {
    param([string]$Uri = $script:OrionHudUrl)

    if (-not (Test-OrionHudEndpoint -Uri $Uri)) {
        throw "Orion HUD endpoint is not healthy; refusing to open an unverified local page."
    }

    Start-Process -FilePath $Uri -ErrorAction Stop | Out-Null
    Write-Host "HUD: opened $Uri"
}

function Stop-OrionOwnedHudBridge {
    param($SessionState = $null)

    if ($null -eq $SessionState -or
        -not ($SessionState.PSObject.Properties.Name -contains "hudStartedByOrion") -or
        $SessionState.hudStartedByOrion -ne $true) {
        Write-Host "HUD bridge: not owned by this Orion launcher session; leaving it alone"
        return
    }

    $current = Get-OrionHudMatchingProcess -SessionState $SessionState
    if ($null -eq $current) {
        Write-Host "HUD bridge: recorded Orion-owned process is gone or no longer matches; leaving other processes alone"
        return
    }

    $handle = Get-OrionHudVerifiedProcessHandle -SessionState $SessionState
    if ($null -eq $handle) {
        Write-Host "HUD bridge: recorded Orion-owned process no longer matches; leaving other processes alone"
        return
    }

    try {
        Write-Host "HUD bridge: stopping Orion-owned PID $($SessionState.hudPid)"
        $handle.Kill()
        if (-not $handle.WaitForExit(5000)) {
            throw "Orion-owned HUD PID $($SessionState.hudPid) did not exit within 5 seconds."
        }
    }
    finally {
        $handle.Dispose()
    }

    if ($null -ne (Get-OrionHudMatchingProcess -SessionState $SessionState)) {
        throw "Orion-owned HUD PID $($SessionState.hudPid) is still running after stop attempt."
    }

    Write-Host "HUD bridge: Orion-owned process stopped"
}
