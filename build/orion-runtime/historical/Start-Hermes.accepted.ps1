$ErrorActionPreference = 'Stop'

$docker = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe"
$dockerDesktop = "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe"
$ollama = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"

function Test-DockerEngine {
    $previousErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'

    try {
        & $docker info --format '{{.ServerVersion}}' 1>$null 2>$null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
    finally {
        $ErrorActionPreference = $previousErrorPreference
    }
}

function Test-OllamaApi {
    try {
        $null = Invoke-RestMethod `
            -Uri 'http://127.0.0.1:11434/api/version' `
            -TimeoutSec 3
        return $true
    }
    catch {
        return $false
    }
}

foreach ($requiredFile in @($docker, $dockerDesktop, $ollama)) {
    if (-not (Test-Path -LiteralPath $requiredFile)) {
        throw "Required application not found: $requiredFile"
    }
}

if (-not (Test-DockerEngine)) {
    Write-Host 'Starting Docker Desktop...'
    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden

    $dockerDeadline = (Get-Date).AddMinutes(2)

    while (-not (Test-DockerEngine)) {
        if ((Get-Date) -ge $dockerDeadline) {
            throw 'Docker Desktop did not become ready within two minutes.'
        }

        Start-Sleep -Seconds 2
    }
}

if (-not (Test-OllamaApi)) {
    Write-Host 'Starting Ollama with a 65,536-token context ceiling...'

    $previousContextLength = $env:OLLAMA_CONTEXT_LENGTH
    $env:OLLAMA_CONTEXT_LENGTH = '65536'

    try {
        Start-Process `
            -FilePath $ollama `
            -ArgumentList 'serve' `
            -WindowStyle Hidden
    }
    finally {
        if ($null -eq $previousContextLength) {
            Remove-Item Env:\OLLAMA_CONTEXT_LENGTH -ErrorAction SilentlyContinue
        }
        else {
            $env:OLLAMA_CONTEXT_LENGTH = $previousContextLength
        }
    }

    $ollamaDeadline = (Get-Date).AddMinutes(1)

    while (-not (Test-OllamaApi)) {
        if ((Get-Date) -ge $ollamaDeadline) {
            throw 'Ollama did not become ready within one minute.'
        }

        Start-Sleep -Seconds 2
    }
}

$showRequest = @{ name = 'qwen3.5-hermes:9b' } | ConvertTo-Json
$modelDetails = Invoke-RestMethod `
    -Uri 'http://127.0.0.1:11434/api/show' `
    -Method Post `
    -ContentType 'application/json' `
    -Body $showRequest `
    -TimeoutSec 10

if ($modelDetails.parameters -notmatch 'num_ctx\s+65536') {
    throw 'The qwen3.5-hermes:9b alias is not configured with num_ctx 65536.'
}

Write-Host 'Docker and Ollama are ready. Starting Hermes...'

$dockerArguments = @(
    'run'
    '-it'
    '--rm'
    '--shm-size=1g'
    '--cap-drop', 'ALL'
    '--cap-add', 'DAC_OVERRIDE'
    '--cap-add', 'CHOWN'
    '--cap-add', 'FOWNER'
    '--cap-add', 'SETUID'
    '--cap-add', 'SETGID'
    '--cap-add', 'KILL'
    '--security-opt', 'no-new-privileges'
    '--pids-limit', '256'
    '--memory=4g'
    '--cpus=2'
    '--dns', '1.1.1.1'
    '--dns', '8.8.8.8'
    '--add-host', 'host.docker.internal:host-gateway'
    '-e', 'HERMES_WRITE_SAFE_ROOT=/opt/data'
    '-v', 'C:\HermesAgent\data:/opt/data'
    '-v', 'C:\Personal\Me:/workspace:ro'
    'hermes-agent-local:v2026.8.18-ddgs'
)

& $docker @dockerArguments

if ($LASTEXITCODE -ne 0) {
    throw "Hermes exited with Docker status $LASTEXITCODE."
}


