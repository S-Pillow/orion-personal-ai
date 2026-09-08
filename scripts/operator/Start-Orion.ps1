[CmdletBinding()]
param(
    [int]$HermesHealthTimeoutSeconds = 30,
    [int]$OllamaHealthTimeoutSeconds = 20
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$stateRoot = Join-Path $env:LOCALAPPDATA "Orion\operator"
$statePath = Join-Path $stateRoot "launcher-session.json"
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

    $tmpPath = "$statePath.tmp"
    $json = $State | ConvertTo-Json -Depth 8
    [IO.File]::WriteAllText($tmpPath, $json, $utf8NoBom)
    Move-Item -LiteralPath $tmpPath -Destination $statePath -Force
}

$hermesHealthUri = "http://127.0.0.1:8642/health"
$ollamaHealthUri = "http://127.0.0.1:11434/api/tags"
$ollamaStartedByOrion = $false
$ollamaPid = $null

try {
    Write-Host "=== START ORION ==="

    $priorState = Read-OrionSessionState
    if ($null -ne $priorState -and
        $priorState.PSObject.Properties.Name -contains "ollamaStartedByOrion" -and
        $priorState.ollamaStartedByOrion -eq $true -and
        $priorState.PSObject.Properties.Name -contains "ollamaPid" -and
        $null -ne $priorState.ollamaPid) {

        $priorOllama = Get-Process -Id ([int]$priorState.ollamaPid) -ErrorAction SilentlyContinue
        if ($null -ne $priorOllama -and $priorOllama.ProcessName -match '^(?i)ollama$') {
            $ollamaStartedByOrion = $true
            $ollamaPid = [int]$priorState.ollamaPid
        }
    }

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

        Write-Host "Ollama: starting"
        $ollamaProcess = Start-Process -FilePath $ollamaCommand.Source -ArgumentList @("serve") -WindowStyle Hidden -PassThru
        $ollamaPid = $ollamaProcess.Id
        $ollamaStartedByOrion = $true

        if (-not (Wait-HttpEndpoint -Uri $ollamaHealthUri -ExpectedUp $true -TimeoutSeconds $OllamaHealthTimeoutSeconds)) {
            try { Stop-Process -Id $ollamaPid -ErrorAction SilentlyContinue } catch {}
            throw "Ollama did not become ready within $OllamaHealthTimeoutSeconds seconds."
        }

        Write-Host "Ollama: ready"
    }

    $hermesCommand = Get-Command "hermes" -CommandType Application -ErrorAction SilentlyContinue
    if ($null -eq $hermesCommand) {
        throw "Hermes executable was not found on PATH."
    }

    if (Test-HttpEndpoint -Uri $hermesHealthUri) {
        Write-Host "Hermes COMPANION: already running"
    }
    else {
        Write-Host "Hermes COMPANION: starting"
        & $hermesCommand.Source -p companion gateway start
        if ($LASTEXITCODE -ne 0) {
            throw "Hermes gateway start exited with code $LASTEXITCODE."
        }

        if (-not (Wait-HttpEndpoint -Uri $hermesHealthUri -ExpectedUp $true -TimeoutSeconds $HermesHealthTimeoutSeconds)) {
            throw "Hermes API did not become healthy within $HermesHealthTimeoutSeconds seconds."
        }

        Write-Host "Hermes COMPANION: ready"
    }

    $state = [ordered]@{
        schemaVersion = 1
        startedAt = (Get-Date).ToString("o")
        ollamaStartedByOrion = $ollamaStartedByOrion
        ollamaPid = $ollamaPid
        hermesHealthUri = $hermesHealthUri
    }
    Write-OrionSessionState -State $state

    Write-Host ""
    Write-Host "ORION READY"
    Write-Host "Hermes API: healthy"
    Write-Host "iai: demand-wake managed by Hermes/iai"
    Start-Sleep -Seconds 3
    exit 0
}
catch {
    Write-Host ""
    Write-Host "START ORION FAILED"
    Write-Host $_.Exception.Message

    if ($ollamaStartedByOrion -and $null -ne $ollamaPid) {
        try {
            $ownedProcess = Get-Process -Id $ollamaPid -ErrorAction SilentlyContinue
            if ($null -ne $ownedProcess -and $ownedProcess.ProcessName -match '^(?i)ollama$') {
                Stop-Process -Id $ollamaPid -ErrorAction SilentlyContinue
            }
        } catch {}
    }

    Start-Sleep -Seconds 10
    exit 1
}
