[CmdletBinding()]
param(
    [int]$HermesHealthTimeoutSeconds = 90,
    [int]$OllamaHealthTimeoutSeconds = 45
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$stateRoot = Join-Path $env:LOCALAPPDATA "Orion\operator"
$statePath = Join-Path $stateRoot "launcher-session.json"
$stateTmpPath = "$statePath.tmp"
$failurePath = Join-Path $stateRoot "last-start-failure.json"
$failureTmpPath = "$failurePath.tmp"
$utf8NoBom = [Text.UTF8Encoding]::new($false)

New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null

function Test-HttpEndpoint {
    param(
        [Parameter(Mandatory=$true)][string]$Uri,
        [int]$TimeoutSeconds = 2
    )

    try {
        $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec $TimeoutSeconds
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
    }
    catch {
        return $false
    }
}

function Wait-HttpEndpoint {
    param(
        [Parameter(Mandatory=$true)][string]$Uri,
        [Parameter(Mandatory=$true)][bool]$ExpectedUp,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $isUp = Test-HttpEndpoint -Uri $Uri
        if ($isUp -eq $ExpectedUp) {
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

function Write-OrionSessionState {
    param([Parameter(Mandatory=$true)]$State)

    $json = $State | ConvertTo-Json -Depth 8
    [IO.File]::WriteAllText($stateTmpPath, $json, $utf8NoBom)
    Move-Item -LiteralPath $stateTmpPath -Destination $statePath -Force
}

function Write-OrionFailureState {
    param(
        [Parameter(Mandatory=$true)][string]$Stage,
        [Parameter(Mandatory=$true)][string]$Message,
        [Parameter(Mandatory=$true)][bool]$HermesStartedByOrion,
        [Parameter(Mandatory=$true)][bool]$OllamaStartedByOrion
    )

    try {
        $failure = [ordered]@{
            schemaVersion = 1
            failedAt = (Get-Date).ToString("o")
            stage = $Stage
            message = $Message
            hermesStartedByOrion = $HermesStartedByOrion
            ollamaStartedByOrion = $OllamaStartedByOrion
        }
        $json = $failure | ConvertTo-Json -Depth 6
        [IO.File]::WriteAllText($failureTmpPath, $json, $utf8NoBom)
        Move-Item -LiteralPath $failureTmpPath -Destination $failurePath -Force
    }
    catch {
        # Failure diagnostics must never interfere with rollback.
    }
}

$hermesHealthUri = "http://127.0.0.1:8642/health"
$ollamaHealthUri = "http://127.0.0.1:11434/api/tags"
$ollamaStartedByOrion = $false
$ollamaPid = $null
$hermesStartedByOrion = $false
$hermesCommand = $null
$stage = "initializing"

try {
    Write-Host "=== START ORION ==="

    $stage = "read-prior-session"
    $priorState = Read-OrionSessionState
    if ($null -ne $priorState -and
        $priorState.PSObject.Properties.Name -contains "ollamaStartedByOrion" -and
        $priorState.ollamaStartedByOrion -eq $true -and
        $priorState.PSObject.Properties.Name -contains "ollamaPid" -and
        $null -ne $priorState.ollamaPid) {

        $priorOllama = Get-Process -Id ([int]$priorState.ollamaPid) -ErrorAction SilentlyContinue
        if ($null -ne $priorOllama -and $priorOllama.ProcessName -match '(?i)^ollama$') {
            $ollamaStartedByOrion = $true
            $ollamaPid = [int]$priorState.ollamaPid
        }
    }

    $stage = "ollama-readiness"
    if (Test-HttpEndpoint -Uri $ollamaHealthUri) {
        Write-Host "Ollama: already available"
    }
    else {
        $ollamaCommand = Get-Command "ollama.exe" -CommandType Application -ErrorAction SilentlyContinue
        if ($null -eq $ollamaCommand) {
            $ollamaCommand = Get-Command "ollama" -CommandType Application -ErrorAction SilentlyContinue
        }
        if ($null -eq $ollamaCommand) {
            throw "Ollama is not running and the ollama executable was not found on PATH."
        }

        $stage = "ollama-start"
        Write-Host "Ollama: starting"
        $ollamaProcess = Start-Process -FilePath $ollamaCommand.Source -ArgumentList @("serve") -WindowStyle Hidden -PassThru
        $ollamaPid = $ollamaProcess.Id
        $ollamaStartedByOrion = $true

        $stage = "ollama-health-wait"
        if (-not (Wait-HttpEndpoint -Uri $ollamaHealthUri -ExpectedUp $true -TimeoutSeconds $OllamaHealthTimeoutSeconds)) {
            throw "Ollama did not become ready within $OllamaHealthTimeoutSeconds seconds."
        }

        Write-Host "Ollama: ready"
    }

    $stage = "hermes-command-discovery"
    $hermesCommand = Get-Command "hermes" -CommandType Application -ErrorAction SilentlyContinue
    if ($null -eq $hermesCommand) {
        throw "Hermes executable was not found on PATH."
    }

    $stage = "hermes-readiness"
    if (Test-HttpEndpoint -Uri $hermesHealthUri) {
        Write-Host "Hermes COMPANION: already running"
    }
    else {
        $stage = "hermes-start"
        Write-Host "Hermes COMPANION: starting"

        # The gateway was not running before this invocation. From this point
        # forward, any gateway that appears is owned by this Start Orion attempt
        # and must be rolled back if the attempt fails.
        $hermesStartedByOrion = $true
        & $hermesCommand.Source -p companion gateway start
        if ($LASTEXITCODE -ne 0) {
            throw "Hermes gateway start exited with code $LASTEXITCODE."
        }

        $stage = "hermes-health-wait"
        if (-not (Wait-HttpEndpoint -Uri $hermesHealthUri -ExpectedUp $true -TimeoutSeconds $HermesHealthTimeoutSeconds)) {
            throw "Hermes API did not become healthy within $HermesHealthTimeoutSeconds seconds."
        }

        Write-Host "Hermes COMPANION: ready"
    }

    $stage = "write-session-state"
    $state = [ordered]@{
        schemaVersion = 1
        startedAt = (Get-Date).ToString("o")
        ollamaStartedByOrion = $ollamaStartedByOrion
        ollamaPid = $ollamaPid
        hermesHealthUri = $hermesHealthUri
    }
    Write-OrionSessionState -State $state

    Remove-Item -LiteralPath $failurePath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $failureTmpPath -Force -ErrorAction SilentlyContinue

    Write-Host ""
    Write-Host "ORION READY"
    Write-Host "Hermes API: healthy"
    Write-Host "iai: demand-wake managed by Hermes/iai"
    Start-Sleep -Seconds 3
    exit 0
}
catch {
    $failureMessage = $_.Exception.Message

    Write-Host ""
    Write-Host "START ORION FAILED"
    Write-Host $failureMessage

    Write-OrionFailureState `
        -Stage $stage `
        -Message $failureMessage `
        -HermesStartedByOrion $hermesStartedByOrion `
        -OllamaStartedByOrion $ollamaStartedByOrion

    # Transactional rollback: stop only the Hermes gateway that this invocation
    # attempted to start. Never stop a gateway that was already healthy before
    # Start Orion ran.
    if ($hermesStartedByOrion -and $null -ne $hermesCommand) {
        try {
            & $hermesCommand.Source -p companion gateway stop | Out-Host
            [void](Wait-HttpEndpoint -Uri $hermesHealthUri -ExpectedUp $false -TimeoutSeconds 30)
        }
        catch {}
    }

    # Stop only the Ollama process owned by Orion. Independently pre-existing
    # Ollama instances remain untouched.
    if ($ollamaStartedByOrion -and $null -ne $ollamaPid) {
        try {
            $ownedProcess = Get-Process -Id $ollamaPid -ErrorAction SilentlyContinue
            if ($null -ne $ownedProcess -and $ownedProcess.ProcessName -match '(?i)^ollama$') {
                Stop-Process -Id $ollamaPid -ErrorAction SilentlyContinue
            }
        }
        catch {}
    }

    Remove-Item -LiteralPath $stateTmpPath -Force -ErrorAction SilentlyContinue

    Start-Sleep -Seconds 10
    exit 1
}
