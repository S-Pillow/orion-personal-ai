[CmdletBinding()]
param(
    [int]$HermesStopTimeoutSeconds = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$stateRoot = Join-Path $env:LOCALAPPDATA "Orion\operator"
$statePath = Join-Path $stateRoot "launcher-session.json"
$hermesHealthUri = "http://127.0.0.1:8642/health"

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
        return $null
    }
}

try {
    Write-Host "=== STOP ORION ==="

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
    if ($null -ne $sessionState -and
        $sessionState.PSObject.Properties.Name -contains "ollamaStartedByOrion" -and
        $sessionState.ollamaStartedByOrion -eq $true -and
        $sessionState.PSObject.Properties.Name -contains "ollamaPid" -and
        $null -ne $sessionState.ollamaPid) {

        $ownedPid = [int]$sessionState.ollamaPid
        $ownedProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $ownedPid" -ErrorAction SilentlyContinue

        if ($null -ne $ownedProcess -and
            ($ownedProcess.Name -match '^(?i)ollama\.exe$' -or $ownedProcess.ExecutablePath -match '(?i)ollama')) {

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
        else {
            Write-Host "Ollama: recorded Orion-owned PID no longer matches a live Ollama process; leaving other Ollama processes alone"
        }
    }
    else {
        Write-Host "Ollama: not owned by this Orion launcher session; leaving it alone"
    }

    if (Test-Path $statePath) {
        Remove-Item -LiteralPath $statePath -Force
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
    exit 1
}
