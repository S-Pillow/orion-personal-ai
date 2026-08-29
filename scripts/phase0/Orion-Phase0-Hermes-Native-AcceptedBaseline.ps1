<#
.SYNOPSIS
  Orion Phase 0 native Hermes baseline - reproducible configuration, verification, and bounded rollback.

.DESCRIPTION
  Records the ACCEPTED Phase 0 Hermes baseline from 2026-08-29.
  This is a recovery/reproduction artifact, not a rule for selecting a future Hermes baseline.
  Future baseline selection must re-resolve the current stable Hermes tag per the Orion Master PRD.

  Accepted evidence snapshot:
    Hermes tag:       v2026.8.27
    Hermes commit:    5fc308a70719a83cccdbba4c0e39c23f5a8239d5
    Hermes package:   0.20.6
    Profile:          companion
    Model:            qwen3.5-hermes:9b
    Provider:         custom
    Base URL:         http://localhost:11434/v1
    API mode:         chat_completions
    API listener:     127.0.0.1:8642
    Windows task:     Hermes_Gateway_companion
    Ollama context:   >= 65536

  This script NEVER runs `hermes update`.
  It NEVER prints API_SERVER_KEY, DISCORD_BOT_TOKEN, or DISCORD_ALLOWED_USERS values.
#>

[CmdletBinding()]
param(
    [ValidateSet('Configure','Verify','Rollback')]
    [string]$Action = 'Verify',

    [string]$DiscordSourceEnvPath,

    [string]$EnvBackupPath,

    [switch]$RemoveGatewayPersistence
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$AcceptedHermesTag    = 'v2026.8.27'
$AcceptedHermesCommit = '5fc308a70719a83cccdbba4c0e39c23f5a8239d5'
$AcceptedVersion      = '0.20.6'
$ProfileId            = 'companion'
$ModelName            = 'qwen3.5-hermes:9b'
$Provider              = 'custom'
$BaseUrl               = 'http://localhost:11434/v1'
$ApiMode               = 'chat_completions'
$ApiHealthUrl          = 'http://127.0.0.1:8642/health'
$ApiChatUrl            = 'http://127.0.0.1:8642/v1/chat/completions'
$TaskName              = 'Hermes_Gateway_companion'

$HermesHome    = Join-Path $env:LOCALAPPDATA 'hermes'
$HermesExe     = Join-Path $HermesHome 'bin\hermes.exe'
$HermesRepo    = Join-Path $HermesHome 'hermes-agent'
$CompanionHome = Join-Path $HermesHome 'profiles\companion'
$EnvPath       = Join-Path $CompanionHome '.env'

function Write-Step {
    param([string]$Text)
    Write-Host ""
    Write-Host "=== $Text ==="
}

function Invoke-Native {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments
    )

    & $FilePath @Arguments
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        throw "Native command failed with exit code $code`: $FilePath $($Arguments -join ' ')"
    }
}

function Assert-File {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label not found: $Path"
    }
}

function Get-EnvMap {
    param([string]$Path)

    $map = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $map
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*#' -or [string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        if ($line -match '^\s*([^=\s]+)\s*=(.*)$') {
            $map[$matches[1]] = $matches[2]
        }
    }
    return $map
}

function Set-EnvValue {
    param(
        [string]$Path,
        [string]$Name,
        [string]$Value
    )

    $lines = @()
    if (Test-Path -LiteralPath $Path) {
        $lines = @(Get-Content -LiteralPath $Path)
    }

    $pattern = '^\s*' + [regex]::Escape($Name) + '\s*='
    $found = $false
    $out = New-Object System.Collections.Generic.List[string]

    foreach ($line in $lines) {
        if ($line -match $pattern) {
            if (-not $found) {
                [void]$out.Add("$Name=$Value")
                $found = $true
            }
        } else {
            [void]$out.Add($line)
        }
    }

    if (-not $found) {
        [void]$out.Add("$Name=$Value")
    }

    [IO.File]::WriteAllLines(
        $Path,
        [string[]]$out,
        (New-Object Text.UTF8Encoding($false))
    )
}

function New-UrlSafeApiKey {
    $bytes = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
}

function Backup-NativeEnv {
    if (-not (Test-Path -LiteralPath $EnvPath)) {
        return $null
    }

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backup = "$EnvPath.orion-phase0-$stamp.bak"
    Copy-Item -LiteralPath $EnvPath -Destination $backup -Force
    return $backup
}

function Get-HermesConfigValue {
    param([string]$Key)
    $value = & $HermesExe -p $ProfileId config get $Key
    if ($LASTEXITCODE -ne 0) {
        throw "Could not read Hermes config key $Key"
    }
    return (($value | Out-String).Trim())
}

function Assert-Equal {
    param([string]$Actual, [string]$Expected, [string]$Label)
    if ($Actual -ne $Expected) {
        throw "$Label mismatch. Expected '$Expected', got '$Actual'."
    }
    Write-Host "$Label`: OK"
}

function Verify-Pin {
    Write-Step 'HERMES PIN'

    Assert-File $HermesExe 'Hermes executable'

    $tag = (& git -C $HermesRepo describe --tags --exact-match 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw 'Hermes checkout is not exactly on a tag.'
    }

    $commit = (& git -C $HermesRepo rev-parse HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not resolve Hermes commit.'
    }

    Assert-Equal $tag $AcceptedHermesTag 'Hermes tag'
    Assert-Equal $commit $AcceptedHermesCommit 'Hermes commit'

    $status = @(& git -C $HermesRepo status --short)
    if ($LASTEXITCODE -ne 0) {
        throw 'Could not inspect Hermes worktree.'
    }
    if ($status.Count -gt 0) {
        throw 'Hermes worktree is not clean.'
    }
    Write-Host 'Hermes worktree: clean'

    $versionText = (& $HermesExe --version | Out-String)
    if ($LASTEXITCODE -ne 0 -or $versionText -notmatch [regex]::Escape($AcceptedVersion)) {
        throw "Hermes version does not contain accepted package version $AcceptedVersion."
    }
    Write-Host "Hermes package version: $AcceptedVersion"
}

function Verify-ProfileConfig {
    Write-Step 'COMPANION PROFILE CONFIG'

    if (-not (Test-Path -LiteralPath $CompanionHome -PathType Container)) {
        throw "Companion profile not found: $CompanionHome"
    }

    Assert-Equal (Get-HermesConfigValue 'model.provider') $Provider 'model.provider'
    Assert-Equal (Get-HermesConfigValue 'model.default') $ModelName 'model.default'
    Assert-Equal (Get-HermesConfigValue 'model.base_url') $BaseUrl 'model.base_url'
    Assert-Equal (Get-HermesConfigValue 'model.api_mode') $ApiMode 'model.api_mode'

    $envMap = Get-EnvMap $EnvPath

    if (-not $envMap.ContainsKey('API_SERVER_ENABLED') -or $envMap['API_SERVER_ENABLED'] -ne 'true') {
        throw 'API_SERVER_ENABLED=true is not present.'
    }
    Write-Host 'API_SERVER_ENABLED: OK'

    if (-not $envMap.ContainsKey('API_SERVER_KEY') -or [string]::IsNullOrWhiteSpace($envMap['API_SERVER_KEY'])) {
        throw 'API_SERVER_KEY is missing or empty.'
    }
    Write-Host "API_SERVER_KEY: present (length $($envMap['API_SERVER_KEY'].Length))"

    if (-not $envMap.ContainsKey('DISCORD_BOT_TOKEN') -or [string]::IsNullOrWhiteSpace($envMap['DISCORD_BOT_TOKEN'])) {
        throw 'DISCORD_BOT_TOKEN is missing or empty.'
    }
    Write-Host 'DISCORD_BOT_TOKEN: present'

    if (-not $envMap.ContainsKey('DISCORD_ALLOWED_USERS') -or [string]::IsNullOrWhiteSpace($envMap['DISCORD_ALLOWED_USERS'])) {
        throw 'DISCORD_ALLOWED_USERS is missing or empty.'
    }
    Write-Host 'DISCORD_ALLOWED_USERS: present'
}

function Verify-Gateway {
    Write-Step 'WINDOWS GATEWAY PERSISTENCE'

    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    if ($task.Principal.RunLevel -notin @('Limited','LeastPrivilege')) {
        throw "Unexpected task RunLevel: $($task.Principal.RunLevel)"
    }

    $trigger = @($task.Triggers | Where-Object { $_.Enabled })
    if ($trigger.Count -lt 1) {
        throw 'Gateway Scheduled Task has no enabled trigger.'
    }

    Write-Host "Task: $TaskName"
    Write-Host "Task state: $($task.State)"
    Write-Host "RunLevel: $($task.Principal.RunLevel)"
    Write-Host "LogonType: $($task.Principal.LogonType)"

    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host "LastRunTime: $($info.LastRunTime)"
    Write-Host "LastTaskResult: $($info.LastTaskResult)"

    $gatewayStatus = (& $HermesExe -p $ProfileId gateway status | Out-String)
    if ($LASTEXITCODE -ne 0 -or $gatewayStatus -notmatch 'Gateway process running') {
        throw 'Hermes companion gateway is not reported running.'
    }
    Write-Host 'Gateway process: running'

    $listener = Get-NetTCPConnection -LocalPort 8642 -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalAddress -eq '127.0.0.1' } |
        Select-Object -First 1

    if (-not $listener) {
        throw '127.0.0.1:8642 is not listening.'
    }
    Write-Host "API listener PID: $($listener.OwningProcess)"
}

function Verify-ApiAndModel {
    Write-Step 'API + LOCAL MODEL'

    $health = Invoke-RestMethod -Uri $ApiHealthUrl -Method Get
    if ($health.status -ne 'ok' -or $health.version -ne $AcceptedVersion) {
        throw 'Unexpected API health response.'
    }
    Write-Host "API health: OK ($($health.version))"

    $envMap = Get-EnvMap $EnvPath
    $apiKey = $envMap['API_SERVER_KEY']

    $headers = @{
        Authorization = "Bearer $apiKey"
        'Content-Type' = 'application/json'
    }

    $body = @{
        model = $ProfileId
        messages = @(
            @{
                role = 'user'
                content = 'Reply with exactly: ORION_PHASE0_VERIFY_OK'
            }
        )
    } | ConvertTo-Json -Depth 5

    $response = Invoke-RestMethod `
        -Uri $ApiChatUrl `
        -Method Post `
        -Headers $headers `
        -Body $body

    $content = [string]$response.choices[0].message.content
    if ($content.Trim() -ne 'ORION_PHASE0_VERIFY_OK') {
        throw "Unexpected model response: '$($content.Trim())'"
    }
    Write-Host 'Authenticated API inference: OK'

    $ollamaPs = (& ollama ps | Out-String)
    if ($LASTEXITCODE -ne 0) {
        throw 'ollama ps failed.'
    }

    $modelLine = ($ollamaPs -split "`r?`n" | Where-Object { $_ -match ('^' + [regex]::Escape($ModelName) + '\s') } | Select-Object -First 1)
    if (-not $modelLine) {
        throw 'Accepted model is not loaded in ollama ps after inference.'
    }

    $numbers = [regex]::Matches($modelLine, '\b\d+\b') | ForEach-Object { [int]$_.Value }
    $context = $numbers | Where-Object { $_ -ge 65536 } | Select-Object -First 1
    if (-not $context) {
        throw "Could not verify Ollama runtime context >= 65536 from: $modelLine"
    }

    Write-Host "Ollama model: $ModelName"
    Write-Host "Ollama runtime context: $context"
}

function Configure-Baseline {
    Write-Step 'CONFIGURE ACCEPTED PHASE 0 BASELINE'

    Assert-File $HermesExe 'Hermes executable'

    if (-not (Test-Path -LiteralPath $CompanionHome -PathType Container)) {
        Write-Host 'Creating companion profile...'
        Invoke-Native $HermesExe 'profile' 'create' $ProfileId
    }

    $backup = Backup-NativeEnv
    if ($backup) {
        Write-Host "Native .env backup created: $backup"
    }

    Invoke-Native $HermesExe '-p' $ProfileId 'config' 'set' 'model.provider' $Provider
    Invoke-Native $HermesExe '-p' $ProfileId 'config' 'set' 'model.default' $ModelName
    Invoke-Native $HermesExe '-p' $ProfileId 'config' 'set' 'model.base_url' $BaseUrl
    Invoke-Native $HermesExe '-p' $ProfileId 'config' 'set' 'model.api_mode' $ApiMode

    if (-not (Test-Path -LiteralPath $EnvPath)) {
        New-Item -ItemType File -Path $EnvPath -Force | Out-Null
    }

    $envMap = Get-EnvMap $EnvPath
    Set-EnvValue $EnvPath 'API_SERVER_ENABLED' 'true'

    if (-not $envMap.ContainsKey('API_SERVER_KEY') -or [string]::IsNullOrWhiteSpace($envMap['API_SERVER_KEY'])) {
        $newKey = New-UrlSafeApiKey
        Set-EnvValue $EnvPath 'API_SERVER_KEY' $newKey
        Remove-Variable newKey
        Write-Host 'API_SERVER_KEY generated locally.'
    } else {
        Write-Host 'API_SERVER_KEY already present; preserved.'
    }

    $envMap = Get-EnvMap $EnvPath
    $discordMissing = (
        -not $envMap.ContainsKey('DISCORD_BOT_TOKEN') -or
        [string]::IsNullOrWhiteSpace($envMap['DISCORD_BOT_TOKEN']) -or
        -not $envMap.ContainsKey('DISCORD_ALLOWED_USERS') -or
        [string]::IsNullOrWhiteSpace($envMap['DISCORD_ALLOWED_USERS'])
    )

    if ($discordMissing -and $DiscordSourceEnvPath) {
        Assert-File $DiscordSourceEnvPath 'Discord source .env'
        $sourceMap = Get-EnvMap $DiscordSourceEnvPath

        foreach ($name in @('DISCORD_BOT_TOKEN','DISCORD_ALLOWED_USERS')) {
            if (-not $sourceMap.ContainsKey($name) -or [string]::IsNullOrWhiteSpace($sourceMap[$name])) {
                throw "$name is missing or empty in DiscordSourceEnvPath."
            }
            Set-EnvValue $EnvPath $name $sourceMap[$name]
        }

        Remove-Variable sourceMap
        Write-Host 'Discord credential variables copied without displaying values.'
    } elseif ($discordMissing) {
        throw 'Discord variables are missing. Re-run with -DiscordSourceEnvPath pointing to a secure local .env.'
    } else {
        Write-Host 'Discord variables already present; preserved.'
    }

    Write-Step 'INSTALL/RECONCILE WINDOWS GATEWAY TASK'
    Invoke-Native $HermesExe '-p' $ProfileId 'gateway' 'install' '--no-start-now' '--start-on-login'

    Write-Host ''
    Write-Host 'Configuration complete.'
    Write-Host 'If UAC handoff occurred, wait for the elevated child to finish before running -Action Verify.'
}

function Rollback-Baseline {
    Write-Step 'ROLLBACK'

    if ([string]::IsNullOrWhiteSpace($EnvBackupPath)) {
        throw '-EnvBackupPath is required for Rollback.'
    }

    Assert-File $EnvBackupPath 'Rollback .env backup'
    Copy-Item -LiteralPath $EnvBackupPath -Destination $EnvPath -Force
    Write-Host 'Companion .env restored from caller-specified backup.'

    if ($RemoveGatewayPersistence) {
        Invoke-Native $HermesExe '-p' $ProfileId 'gateway' 'uninstall'
        Write-Host 'Gateway persistence removal requested.'
    }

    Write-Host 'Rollback complete. No Hermes update was performed.'
}

function Verify-Baseline {
    Verify-Pin
    Verify-ProfileConfig
    Verify-Gateway
    Verify-ApiAndModel

    Write-Step 'DISCORD MANUAL ACCEPTANCE'
    Write-Host 'Configuration presence is verified.'
    Write-Host 'A real Discord round-trip remains the authoritative functional check.'
    Write-Host 'Accepted post-restart phrase on 2026-08-29: ORION_POST_RESTART_OK'

    Write-Step 'RESULT'
    Write-Host 'PASS: automated Phase 0 native Hermes verification completed.'
}

$parseTokens = $null
$parseErrors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile(
    $PSCommandPath,
    [ref]$parseTokens,
    [ref]$parseErrors
)
if ($parseErrors.Count -gt 0) {
    $messages = ($parseErrors | ForEach-Object { $_.Message }) -join '; '
    throw "PowerShell parser gate failed: $messages"
}
Write-Host 'PowerShell parser gate: PASS'

switch ($Action) {
    'Configure' { Configure-Baseline }
    'Verify'    { Verify-Baseline }
    'Rollback'  { Rollback-Baseline }
}
