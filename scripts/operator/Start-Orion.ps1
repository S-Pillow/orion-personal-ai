[CmdletBinding()]
param(
    [int]$HermesHealthTimeoutSeconds = 30,
    [int]$OllamaHealthTimeoutSeconds = 60,
    [int]$HudHealthTimeoutSeconds = 15
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$stateRoot = Join-Path $env:LOCALAPPDATA "Orion\operator"
$statePath = Join-Path $stateRoot "launcher-session.json"
$logRoot = Join-Path $stateRoot "logs"
$orionRoot = Split-Path -Parent $PSScriptRoot
$hudRoot = Join-Path $orionRoot "hud"
$hudHelperPath = Join-Path $PSScriptRoot "Hud-Operator.ps1"
$utf8NoBom = [Text.UTF8Encoding]::new($false)
$ollamaLaunchLibrary = "rocm_v7_1"

New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null

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

function Wait-DirectHttpEndpoint {
    param(
        [Parameter(Mandatory=$true)][string]$Uri,
        [Parameter(Mandatory=$true)][bool]$ExpectedUp,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $isUp = Test-DirectHttpEndpoint -Uri $Uri
        if ($isUp -eq $ExpectedUp) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    return $false
}

function Get-ListenerOwnerPid {
    param([Parameter(Mandatory=$true)][int]$Port)

    try {
        $listeners = @(
            Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        )
        if ($listeners.Count -gt 0) {
            return [int]$listeners[0].OwningProcess
        }
    }
    catch {}

    return $null
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
$ollamaLibraryUsed = $null
$ollamaStdoutPath = $null
$ollamaStderrPath = $null

try {
    Write-Host "=== START ORION ==="

    if (-not (Test-Path -LiteralPath $hudHelperPath)) {
        throw "Installed Orion HUD operator helper is missing: $hudHelperPath"
    }
    . $hudHelperPath

    $priorState = Read-OrionSessionState
    if ($null -ne $priorState -and
        $priorState.PSObject.Properties.Name -contains "ollamaDescendants" -and
        $null -ne $priorState.ollamaDescendants -and
        @($priorState.ollamaDescendants).Count -gt 0) {
        throw "Pending Orion-owned Ollama descendant cleanup exists. Run Stop Orion again before Start Orion."
    }

    $priorHudOwned = $false
    if ($null -ne $priorState -and
        $priorState.PSObject.Properties.Name -contains "hudStartedByOrion" -and
        $priorState.hudStartedByOrion -eq $true) {

        foreach ($requiredHudField in @(
            "hudPid",
            "hudProcessName",
            "hudExecutablePath",
            "hudCreationDate",
            "hudBridgePath"
        )) {
            if (-not ($priorState.PSObject.Properties.Name -contains $requiredHudField) -or
                $null -eq $priorState.$requiredHudField -or
                [string]::IsNullOrWhiteSpace([string]$priorState.$requiredHudField)) {
                throw "Persisted Orion-owned HUD state is incomplete. Run Stop Orion before retrying Start Orion."
            }
        }
        $priorHudOwned = $true
    }

    if ($null -ne $priorState -and
        $priorState.PSObject.Properties.Name -contains "ollamaStartedByOrion" -and
        $priorState.ollamaStartedByOrion -eq $true -and
        $priorState.PSObject.Properties.Name -contains "ollamaPid" -and
        $null -ne $priorState.ollamaPid) {

        $priorOllama = Get-Process -Id ([int]$priorState.ollamaPid) -ErrorAction SilentlyContinue
        if ($null -ne $priorOllama -and $priorOllama.ProcessName -match '^(?i)ollama$') {
            $ollamaStartedByOrion = $true
            $ollamaPid = [int]$priorState.ollamaPid
            if ($priorState.PSObject.Properties.Name -contains "ollamaLibrary" -and
                $null -ne $priorState.ollamaLibrary) {
                $ollamaLibraryUsed = [string]$priorState.ollamaLibrary
            }
        }
    }

    if (Test-DirectHttpEndpoint -Uri $ollamaHealthUri) {
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

        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $ollamaStdoutPath = Join-Path $logRoot "ollama-$stamp.stdout.log"
        $ollamaStderrPath = Join-Path $logRoot "ollama-$stamp.stderr.log"

        Write-Host "Ollama: starting"
        Write-Host "Ollama backend: $ollamaLaunchLibrary"

        $previousOllamaLibrary = $env:OLLAMA_LLM_LIBRARY
        try {
            $env:OLLAMA_LLM_LIBRARY = $ollamaLaunchLibrary
            $ollamaProcess = Start-Process `
                -FilePath $ollamaCommand.Source `
                -ArgumentList @("serve") `
                -WindowStyle Hidden `
                -RedirectStandardOutput $ollamaStdoutPath `
                -RedirectStandardError $ollamaStderrPath `
                -PassThru
        }
        finally {
            $env:OLLAMA_LLM_LIBRARY = $previousOllamaLibrary
        }

        $ollamaPid = $ollamaProcess.Id
        $ollamaStartedByOrion = $true
        $ollamaLibraryUsed = $ollamaLaunchLibrary

        if (-not (Wait-DirectHttpEndpoint -Uri $ollamaHealthUri -ExpectedUp $true -TimeoutSeconds $OllamaHealthTimeoutSeconds)) {
            $ollamaProcess.Refresh()
            $listenerOwnerPid = Get-ListenerOwnerPid -Port 11434

            if ($ollamaProcess.HasExited) {
                throw "Ollama exited before becoming healthy (exit code $($ollamaProcess.ExitCode)). Backend: $ollamaLibraryUsed. Logs: $ollamaStdoutPath ; $ollamaStderrPath"
            }

            if ($null -ne $listenerOwnerPid) {
                throw "Ollama bound port 11434 but direct health checks failed. Listener PID: $listenerOwnerPid. Backend: $ollamaLibraryUsed. Logs: $ollamaStdoutPath ; $ollamaStderrPath"
            }

            throw "Ollama did not bind port 11434 or become healthy within $OllamaHealthTimeoutSeconds seconds. Backend: $ollamaLibraryUsed. Logs: $ollamaStdoutPath ; $ollamaStderrPath"
        }

        Write-Host "Ollama: ready ($ollamaLibraryUsed)"
    }

    $hermesCommand = Get-Command "hermes" -CommandType Application -ErrorAction SilentlyContinue
    if ($null -eq $hermesCommand) {
        throw "Hermes executable was not found on PATH."
    }

    if (Test-DirectHttpEndpoint -Uri $hermesHealthUri) {
        Write-Host "Hermes COMPANION: already running"
    }
    else {
        Write-Host "Hermes COMPANION: starting"
        & $hermesCommand.Source -p companion gateway start
        if ($LASTEXITCODE -ne 0) {
            throw "Hermes gateway start exited with code $LASTEXITCODE."
        }

        if (-not (Wait-DirectHttpEndpoint -Uri $hermesHealthUri -ExpectedUp $true -TimeoutSeconds $HermesHealthTimeoutSeconds)) {
            throw "Hermes API did not become healthy within $HermesHealthTimeoutSeconds seconds."
        }

        Write-Host "Hermes COMPANION: ready"
    }

    # Persist a recoverable runtime state before introducing HUD launch failure points.
    $state = [ordered]@{
        schemaVersion = 2
        startedAt = (Get-Date).ToString("o")
        ollamaStartedByOrion = $ollamaStartedByOrion
        ollamaPid = $ollamaPid
        ollamaLibrary = $ollamaLibraryUsed
        ollamaDescendants = @()
        hermesHealthUri = $hermesHealthUri
        hudStartedByOrion = $false
        hudPid = $null
        hudProcessName = $null
        hudExecutablePath = $null
        hudCreationDate = $null
        hudBridgePath = $null
        hudUrl = $script:OrionHudUrl
    }

    if ($priorHudOwned) {
        $state["hudStartedByOrion"] = $true
        $state["hudPid"] = [int]$priorState.hudPid
        $state["hudProcessName"] = [string]$priorState.hudProcessName
        $state["hudExecutablePath"] = [string]$priorState.hudExecutablePath
        $state["hudCreationDate"] = [string]$priorState.hudCreationDate
        $state["hudBridgePath"] = [string]$priorState.hudBridgePath
    }
    Write-OrionSessionState -State $state

    $hud = $null
    $hudOwnershipPersisted = $false
    try {
        $hud = Start-OrionHudBridge `
            -HudRoot $hudRoot `
            -LogRoot $logRoot `
            -PriorState $priorState `
            -TimeoutSeconds $HudHealthTimeoutSeconds

        $state["hudStartedByOrion"] = [bool]$hud.StartedByOrion
        $state["hudPid"] = $hud.ProcessId
        $state["hudProcessName"] = $hud.ProcessName
        $state["hudExecutablePath"] = $hud.ExecutablePath
        $state["hudCreationDate"] = if ($null -eq $hud.CreationDate) {
            $null
        }
        else {
            ([datetime]$hud.CreationDate).ToString("o")
        }
        $state["hudBridgePath"] = [string]$hud.BridgePath
        $state["hudUrl"] = [string]$hud.Url
        Write-OrionSessionState -State $state
        $hudOwnershipPersisted = $true

        Open-OrionHud -Uri ([string]$hud.Url)
    }
    catch {
        $hudFailureMessage = $_.Exception.Message
        $hudRollbackFailure = $null

        if ($null -ne $hud -and $hud.StartedByOrion -eq $true) {
            $hudCleanupState = [PSCustomObject]@{
                hudStartedByOrion = $true
                hudPid = $hud.ProcessId
                hudProcessName = $hud.ProcessName
                hudExecutablePath = $hud.ExecutablePath
                hudCreationDate = if ($null -eq $hud.CreationDate) {
                    $null
                }
                else {
                    ([datetime]$hud.CreationDate).ToString("o")
                }
                hudBridgePath = $hud.BridgePath
            }

            try {
                Stop-OrionOwnedHudBridge -SessionState $hudCleanupState
            }
            catch {
                $hudRollbackFailure = $_.Exception.Message
            }
        }

        Write-Host ""
        Write-Host "START ORION FAILED"
        Write-Host "Ollama and Hermes are healthy, but the accepted HUD could not be started/opened."
        Write-Host $hudFailureMessage

        if ($null -ne $hudRollbackFailure) {
            Write-Host "HUD rollback also failed: $hudRollbackFailure"
            if (-not $hudOwnershipPersisted) {
                Write-Host "HUD ownership could not be persisted before rollback failed. Do not rerun Start Orion until the HUD process on port 8765 is reconciled."
            }
            else {
                Write-Host "Persisted HUD ownership remains available for a Stop Orion retry."
            }
        }
        elseif ($null -ne $hud -and $hud.StartedByOrion -eq $true) {
            Write-Host "Newly started Orion HUD bridge was identity-verified and rolled back."
        }

        Write-Host "Launcher session state was preserved. Run Stop Orion to return to clean-off before retrying."
        exit 1
    }

    Write-Host ""
    Write-Host "ORION READY"
    Write-Host "Ollama API: healthy"
    if ($null -ne $ollamaLibraryUsed) {
        Write-Host "Ollama backend: $ollamaLibraryUsed"
    }
    Write-Host "Hermes API: healthy"
    Write-Host "HUD: $($state['hudUrl'])"
    if ($state["hudStartedByOrion"] -eq $true) {
        Write-Host "HUD bridge ownership: Orion-owned PID $($state['hudPid'])"
    }
    else {
        Write-Host "HUD bridge ownership: pre-existing / unclaimed"
    }
    Write-Host "iai: demand-wake managed by Hermes/iai"
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

    exit 1
}
