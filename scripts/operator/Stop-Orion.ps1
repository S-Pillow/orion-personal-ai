[CmdletBinding()]
param(
    [int]$HermesStopTimeoutSeconds = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$stateRoot = Join-Path $env:LOCALAPPDATA "Orion\operator"
$statePath = Join-Path $stateRoot "launcher-session.json"
$hermesHealthUri = "http://127.0.0.1:8642/health"

function Test-HermesHealth {
    try {
        $response = Invoke-WebRequest -Uri $hermesHealthUri -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
    }
    catch {
        return $false
    }
}

function Wait-HermesDown {
    param([int]$TimeoutSeconds = 30)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (-not (Test-HermesHealth)) {
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
            Start-Sleep -Seconds 2

            if (Get-Process -Id $ownedPid -ErrorAction SilentlyContinue) {
                Stop-Process -Id $ownedPid -Force -ErrorAction SilentlyContinue
            }
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
    Write-Host "iai will remain under its vendor idle/HIBERNATION lifecycle."
    Start-Sleep -Seconds 3
    exit 0
}
catch {
    Write-Host ""
    Write-Host "STOP ORION FAILED"
    Write-Host $_.Exception.Message
    Start-Sleep -Seconds 10
    exit 1
}
