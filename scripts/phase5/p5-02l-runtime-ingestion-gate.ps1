param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("I_AUTHORIZE_P5_02L_RUNTIME_INGESTION")]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# P5-02L starts only the Hermes COMPANION gateway, verifies runtime ingestion,
# and returns Hermes to manual-off. It does not start/stop Ollama, mutate real
# vault/inbox content, enable production mutation mode, or register a new tool.

$HermesHome = Join-Path $env:LOCALAPPDATA "hermes"
$HermesCheckout = Join-Path $HermesHome "hermes-agent"
$Hermes = Join-Path $HermesCheckout "venv\Scripts\hermes.exe"
$HermesPython = Join-Path $HermesCheckout "venv\Scripts\python.exe"
$HermesPatchedApi = Join-Path $HermesCheckout "gateway\platforms\api_server.py"

$Profile = Join-Path $HermesHome "profiles\companion"
$Config = Join-Path $Profile "config.yaml"
$EnvFile = Join-Path $Profile ".env"
$PluginDest = Join-Path $Profile "plugins\orion-vault-actions"
$PluginInit = Join-Path $PluginDest "__init__.py"
$RecoveryRoot = Join-Path $Profile "orion\production-recovery"
$RuntimeVerifier = Join-Path $PSScriptRoot "p5-02l-runtime-ingestion-verify.py"

$ExpectedConfigHash = "34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7"
$ExpectedPluginInitHash = "FCFA3DDC4A86B99691FB003CF4421027C5CC3CA22AC99ADBCCEEE8D3B3C7B5DA"
$ExpectedHermesCommit = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedPatchedApiHash = "ECFD6DD53610C24A81F078650A0B2B3E129478A50FDB5F353313FFF6E12E3888"
$GatewayHealthTimeoutSeconds = 150

$RecoveryEnvName = "ORION_P5_PRODUCTION_RECOVERY_ROOT"
$ForbiddenNames = @(
    "ORION_P5_MUTATION_MODE",
    "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
    "ORION_P5_RECOVERY_ROOT"
)

function Test-GatewayHealth {
    $uri = "http" + "://127.0.0.1:8642/health"
    try {
        $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
    }
    catch {
        return $false
    }
}

function Wait-GatewayState {
    param(
        [Parameter(Mandatory = $true)][bool]$ExpectedUp,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if ((Test-GatewayHealth) -eq $ExpectedUp) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Get-EnvText {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "STOP: COMPANION .env missing."
    }

    $bytes = [IO.File]::ReadAllBytes($Path)
    if ($bytes -contains [byte]0) {
        throw "STOP: COMPANION .env contains NUL bytes."
    }

    $encoding = [Text.UTF8Encoding]::new($false, $true)
    $text = $encoding.GetString($bytes)
    if ($text.Length -gt 0 -and $text[0] -eq [char]0xFEFF) {
        $text = $text.Substring(1)
    }
    return $text
}

function Get-ActiveEnvValues {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $escaped = [regex]::Escape($Name)
    $values = @()
    foreach ($line in ($Text -split "\r\n|\n|\r")) {
        if ($line -match "^\s*#") {
            continue
        }
        if ($line -match ("^\s*" + $escaped + "\s*=\s*(.*)$")) {
            $values += $Matches[1].Trim()
        }
    }
    return @($values)
}

if ($AuthorizationToken -ne "I_AUTHORIZE_P5_02L_RUNTIME_INGESTION") {
    throw "STOP: explicit P5-02L authorization token required."
}

foreach ($file in @(
    $Hermes,
    $HermesPython,
    $HermesPatchedApi,
    $Config,
    $EnvFile,
    $PluginInit,
    $RuntimeVerifier
)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "STOP: required file missing: $file"
    }
}

if (-not (Test-Path -LiteralPath $RecoveryRoot -PathType Container)) {
    throw "STOP: accepted production recovery root missing."
}

if (Test-GatewayHealth) {
    throw "STOP: Hermes gateway already running; P5-02L requires manual-off baseline."
}

$ConfigBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash
$EnvBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash
$PluginBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash
$PatchedApiHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $HermesPatchedApi).Hash

if ($ConfigBefore -ne $ExpectedConfigHash) {
    throw "STOP: COMPANION config hash differs from accepted baseline."
}
if ($PluginBefore -ne $ExpectedPluginInitHash) {
    throw "STOP: installed Orion plugin hash differs from accepted baseline."
}
if ($PatchedApiHash -ne $ExpectedPatchedApiHash) {
    throw "STOP: accepted P4-04A Hermes API patch hash differs."
}

$HermesHead = (& git -C $HermesCheckout rev-parse HEAD 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $HermesHead -ne $ExpectedHermesCommit) {
    throw "STOP: Hermes checkout commit differs from accepted runtime."
}

foreach ($name in @($RecoveryEnvName) + $ForbiddenNames) {
    $value = [Environment]::GetEnvironmentVariable($name, "Process")
    if (-not [string]::IsNullOrWhiteSpace($value)) {
        throw "STOP: unexpected ambient process setting present: $name"
    }
}

$EnvText = Get-EnvText -Path $EnvFile
$RecoveryValues = @(Get-ActiveEnvValues -Text $EnvText -Name $RecoveryEnvName)

if ($RecoveryValues.Count -ne 1) {
    throw "STOP: expected exactly one persisted production recovery-root assignment."
}
if ($RecoveryValues[0] -ne $RecoveryRoot) {
    throw "STOP: persisted production recovery-root value mismatch."
}
foreach ($name in $ForbiddenNames) {
    if (@(Get-ActiveEnvValues -Text $EnvText -Name $name).Count -ne 0) {
        throw "STOP: forbidden persistent mutation/disposable setting present: $name"
    }
}

$RecoveryChildren = @(Get-ChildItem -LiteralPath $RecoveryRoot -Force)
if ($RecoveryChildren.Count -ne 0) {
    throw "STOP: production recovery root is not empty before runtime start."
}

Write-Host "P5_02L_PERSISTED_RECOVERY_ROOT_PRECHECK=PASS"
Write-Host "P5_02L_MUTATION_MODE_PERSISTED=false"
Write-Host "P5_02L_DISPOSABLE_FLAGS_PERSISTED=false"
Write-Host "P5_02L_HERMES_SOURCE_PIN_MATCH=true"
Write-Host "P5_02L_P4_04A_PATCH_MATCH=true"

$Started = $false
$Validated = $false
$Stopped = $false

try {
    Write-Host ""
    Write-Host "=== P5-02L START COMPANION ==="

    & $Hermes -p companion gateway start
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: Hermes COMPANION gateway start failed."
    }
    $Started = $true

    Write-Host "P5_02L_GATEWAY_HEALTH_TIMEOUT_SECONDS=$GatewayHealthTimeoutSeconds"

    if (-not (Wait-GatewayState -ExpectedUp $true -TimeoutSeconds $GatewayHealthTimeoutSeconds)) {
        throw "STOP: Hermes gateway did not become healthy within $GatewayHealthTimeoutSeconds seconds."
    }

    & $Hermes -p companion gateway status

    Write-Host "P5_02L_GATEWAY_HEALTHY=true"

    # This verifier uses the same accepted Hermes dotenv loader with the
    # COMPANION profile and queries the live authenticated /v1/toolsets route.
    & $HermesPython $RuntimeVerifier $Profile $PluginDest $RecoveryRoot
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: P5-02L live runtime-ingestion verifier failed."
    }

    $Validated = $true
}
finally {
    if ($Started -or (Test-GatewayHealth)) {
        Write-Host ""
        Write-Host "=== P5-02L STOP COMPANION ==="
        & $Hermes -p companion gateway stop
        $StopExit = $LASTEXITCODE

        if (-not (Wait-GatewayState -ExpectedUp $false -TimeoutSeconds 30)) {
            Write-Host "P5_02L_GATEWAY_STOP_VERIFICATION=FAIL"
            throw "STOP: Hermes gateway remained reachable after stop."
        }

        if ($StopExit -ne 0) {
            Write-Host "P5_02L_GATEWAY_STOP_NONZERO_BUT_DOWN=true"
        }

        $Stopped = $true
        Write-Host "P5_02L_GATEWAY_STOPPED=true"
    }
}

if (-not $Validated) {
    throw "STOP: runtime ingestion was not validated."
}
if (-not $Stopped) {
    throw "STOP: Hermes manual-off restoration was not completed."
}

$ConfigAfter = (Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash
$EnvAfter = (Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash
$PluginAfter = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash
$PatchedApiAfter = (Get-FileHash -Algorithm SHA256 -LiteralPath $HermesPatchedApi).Hash

if ($ConfigAfter -ne $ConfigBefore) {
    throw "STOP: COMPANION config changed during P5-02L."
}
if ($EnvAfter -ne $EnvBefore) {
    throw "STOP: COMPANION .env changed during P5-02L."
}
if ($PluginAfter -ne $PluginBefore) {
    throw "STOP: installed Orion plugin changed during P5-02L."
}
if ($PatchedApiAfter -ne $PatchedApiHash) {
    throw "STOP: P4-04A Hermes API patch changed during P5-02L."
}

if (Test-GatewayHealth) {
    throw "STOP: Hermes gateway unexpectedly reachable after manual-off restoration."
}

$RecoveryChildrenAfter = @(Get-ChildItem -LiteralPath $RecoveryRoot -Force)
if ($RecoveryChildrenAfter.Count -ne 0) {
    throw "STOP: runtime start created unexpected production recovery records."
}

Write-Host "P5_02L_CONFIG_UNCHANGED=true"
Write-Host "P5_02L_ENV_UNCHANGED=true"
Write-Host "P5_02L_PLUGIN_UNCHANGED=true"
Write-Host "P5_02L_RECOVERY_ROOT_STILL_EMPTY=true"
Write-Host "P5_02L_MUTATION_INVOCATION=false"
Write-Host "HERMES_MANUAL_OFF=true"
Write-Host "P5_02L_RUNTIME_INGESTION_LIFECYCLE=PASS"
