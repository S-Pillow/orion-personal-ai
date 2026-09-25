param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("I_AUTHORIZE_P5_02T_EXACT_PRODUCTION_MOVE")]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# P5-02T performs exactly one authorized production mutation:
# move the frozen P5-02S controlled Orion draft from the accepted inbox path
# to the accepted vault path through the registered guarded apply tool.
#
# The mutation mode exists only inside the child Python process around the one
# registered apply dispatch. This wrapper never persists mutation mode, never
# starts Hermes gateway, never auto-restores the source, never deletes the
# target, and never cleans recovery evidence on failure.

$QualifiedSourceCommit = "faf8b4787d8e6fb668eb5e9d754104910b4b401a"
$ExpectedBranch = "feature/orion-phase5-p5-02t-first-production-move"
$ExpectedConfigHash = "34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7"
$ExpectedSourceHash = "132FF51D62FD7FD8827D7222E233617E92C55DC21D40FF68164F2238BA0FD132"
$ExpectedEditCanaryHash = "DDB08A8CA9AB5D06185A692182A742210817CBA1D5523C841D6A371DFDB57B4C"
$ExpectedRecoveryIds = @(
    "1b1e26014063b3156adb2152c703371bf5c78234af9dfe9ab51e045e652d7b27",
    "33d3dc72984b872778680106dabfc2260eab9a91be130b9e9d6dd1351483de3f"
)

$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$HermesHome = Join-Path $env:LOCALAPPDATA "hermes"
$HermesCheckout = Join-Path $HermesHome "hermes-agent"
$Hermes = Join-Path $HermesCheckout "venv\Scripts\hermes.exe"
$HermesPython = Join-Path $HermesCheckout "venv\Scripts\python.exe"

$Profile = Join-Path $HermesHome "profiles\companion"
$Config = Join-Path $Profile "config.yaml"
$EnvFile = Join-Path $Profile ".env"
$PluginDest = Join-Path $Profile "plugins\orion-vault-actions"
$PluginInit = Join-Path $PluginDest "__init__.py"
$PluginManifest = Join-Path $PluginDest "plugin.yaml"
$RecoveryRoot = Join-Path $Profile "orion\production-recovery"

$Source = "C:\Personal\Orion-Inbox\_Orion-P5-Move-Canary.md"
$Target = "C:\Personal\Me\_Orion-P5-Move-Canary.md"
$EditCanary = "C:\Personal\Me\_Orion-P5-Canary.md"
$Runner = Join-Path $PSScriptRoot "p5-02t-first-production-move.py"

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$SourceWorktree = Join-Path $env:TEMP "orion-p5-02t-source-$Stamp"

function Test-GatewayHealth {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8642/health" -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
    }
    catch {
        return $false
    }
}

function Get-EnvText {
    param([Parameter(Mandatory = $true)][string]$Path)

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

if ($AuthorizationToken -ne "I_AUTHORIZE_P5_02T_EXACT_PRODUCTION_MOVE") {
    throw "STOP: exact P5-02T production-move authorization token required."
}

foreach ($file in @(
    $Hermes,
    $HermesPython,
    $Config,
    $EnvFile,
    $PluginInit,
    $PluginManifest,
    $Source,
    $EditCanary,
    $Runner
)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "STOP: required file missing: $file"
    }
}
if (-not (Test-Path -LiteralPath $RecoveryRoot -PathType Container)) {
    throw "STOP: production recovery root missing."
}
if (Test-Path -LiteralPath $Target) {
    throw "STOP: frozen P5-02T target already exists."
}

if (Test-GatewayHealth) {
    throw "STOP: Hermes gateway is running; P5-02T requires manual-off baseline."
}

$RepoStatus = (& git -C $Repo status --porcelain=v1 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoStatus) {
    throw "STOP: Orion repository working tree is not clean."
}
$RepoBranch = (& git -C $Repo branch --show-current 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $RepoBranch -ne $ExpectedBranch) {
    throw "STOP: expected P5-02T branch is not checked out."
}

$CommitObject = $QualifiedSourceCommit + "^{commit}"
& git -C $Repo cat-file -e $CommitObject
if ($LASTEXITCODE -ne 0) {
    throw "STOP: exact P5-02N qualified source commit is unavailable locally."
}

foreach ($name in @(
    "ORION_P5_PRODUCTION_RECOVERY_ROOT",
    "ORION_P5_MUTATION_MODE",
    "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
    "ORION_P5_RECOVERY_ROOT"
)) {
    if (-not [string]::IsNullOrWhiteSpace(
        [Environment]::GetEnvironmentVariable($name, "Process")
    )) {
        throw "STOP: unexpected ambient Phase 5 process setting present: $name"
    }
}

$ConfigBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash
$EnvBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash
$PluginInitBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash
$PluginManifestBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginManifest).Hash
$SourceHashBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $Source).Hash
$EditCanaryHashBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $EditCanary).Hash

if ($ConfigBefore -ne $ExpectedConfigHash) {
    throw "STOP: COMPANION config differs from accepted baseline."
}
if ($SourceHashBefore -ne $ExpectedSourceHash) {
    throw "STOP: controlled move source differs from frozen P5-02S hash."
}
if ($EditCanaryHashBefore -ne $ExpectedEditCanaryHash) {
    throw "STOP: edit canary differs from accepted P5-02R restored state."
}

$EnvText = Get-EnvText -Path $EnvFile
foreach ($name in @(
    "ORION_P5_MUTATION_MODE",
    "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
    "ORION_P5_RECOVERY_ROOT"
)) {
    if (@(Get-ActiveEnvValues -Text $EnvText -Name $name).Count -ne 0) {
        throw "STOP: forbidden persistent mutation/disposable setting present: $name"
    }
}

$RecoveryValues = @(
    Get-ActiveEnvValues -Text $EnvText -Name "ORION_P5_PRODUCTION_RECOVERY_ROOT"
)
if ($RecoveryValues.Count -ne 1 -or $RecoveryValues[0] -ne $RecoveryRoot) {
    throw "STOP: persisted production recovery-root assignment mismatch."
}

$RecoveryEntriesBefore = @(Get-ChildItem -LiteralPath $RecoveryRoot -Force)
if ($RecoveryEntriesBefore.Count -ne 2) {
    throw "STOP: production recovery root must contain exactly two accepted records before P5-02T."
}
if (@($RecoveryEntriesBefore | Where-Object { -not $_.PSIsContainer }).Count -ne 0) {
    throw "STOP: unexpected non-directory entry exists in production recovery root."
}
$RecoveryIdsBefore = @(
    $RecoveryEntriesBefore | Select-Object -ExpandProperty Name
) | Sort-Object
if (($RecoveryIdsBefore -join "|") -ne (($ExpectedRecoveryIds | Sort-Object) -join "|")) {
    throw "STOP: production recovery inventory differs from accepted P5-02R state."
}

try {
    & git -C $Repo worktree add --detach $SourceWorktree $QualifiedSourceCommit
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: could not create exact qualified-source worktree."
    }

    $SourcePlugin = Join-Path $SourceWorktree "hermes_plugins\orion-vault-actions"
    $SourceInit = Join-Path $SourcePlugin "__init__.py"
    $SourceManifest = Join-Path $SourcePlugin "plugin.yaml"

    if (
        $PluginInitBefore -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $SourceInit).Hash
    ) {
        throw "STOP: installed Orion plugin code differs from qualified P5-02N source."
    }
    if (
        $PluginManifestBefore -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $SourceManifest).Hash
    ) {
        throw "STOP: installed Orion plugin manifest differs from qualified P5-02N source."
    }

    & $Hermes -p companion plugins doctor $PluginDest --ci
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: installed-location plugin doctor failed."
    }

    & $HermesPython -m py_compile $Runner
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: P5-02T runner compile check failed."
    }

    Write-Host "P5_02T_PRECHECK=PASS"
    Write-Host "P5_02T_INSTALLED_SOURCE_MATCH=true"
    Write-Host "P5_02T_INSTALLED_PLUGIN_DOCTOR=PASS"
    Write-Host "P5_02T_RUNNER_COMPILE=PASS"
    Write-Host "P5_02T_SOURCE_SHA256=$SourceHashBefore"
    Write-Host "P5_02T_TARGET_STATE_BEFORE=absent"
    Write-Host "P5_02T_PRODUCTION_RECOVERY_COUNT_BEFORE=2"
    Write-Host "P5_02T_MUTATION_MODE_PERSISTED=false"
    Write-Host "P5_02T_HERMES_MANUAL_OFF=true"
    Write-Host ""
    Write-Host "The child process will show exactly one Orion production move approval prompt."
    Write-Host "Verify source, target, source hash/file ID, and exact diff. Choose ONCE only."
    Write-Host "Any other choice must fail closed."
    Write-Host ""

    & $HermesPython $Runner $Profile $PluginDest $RecoveryRoot
    $ChildExit = $LASTEXITCODE

    $SourceStateAfter = if (Test-Path -LiteralPath $Source) {
        "present"
    } else {
        "absent"
    }
    $TargetHashAfter = if (Test-Path -LiteralPath $Target -PathType Leaf) {
        (Get-FileHash -Algorithm SHA256 -LiteralPath $Target).Hash
    } elseif (Test-Path -LiteralPath $Target) {
        "NOT_A_FILE"
    } else {
        "MISSING"
    }
    $RecoveryCountAfter = @(Get-ChildItem -LiteralPath $RecoveryRoot -Force).Count

    Write-Host "P5_02T_PARENT_CHILD_EXIT=$ChildExit"
    Write-Host "P5_02T_PARENT_SOURCE_STATE=$SourceStateAfter"
    Write-Host "P5_02T_PARENT_TARGET_SHA256=$TargetHashAfter"
    Write-Host "P5_02T_PARENT_RECOVERY_COUNT=$RecoveryCountAfter"
    Write-Host "P5_02T_PARENT_AUTOMATIC_RESTORE=false"
    Write-Host "P5_02T_PARENT_AUTOMATIC_TARGET_DELETE=false"

    if (Test-GatewayHealth) {
        throw "STOP: P5-02T unexpectedly started Hermes gateway."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash -ne $ConfigBefore) {
        throw "STOP: P5-02T changed COMPANION config."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $EnvFile).Hash -ne $EnvBefore) {
        throw "STOP: P5-02T changed COMPANION .env."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash -ne $PluginInitBefore) {
        throw "STOP: P5-02T changed installed plugin code."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $PluginManifest).Hash -ne $PluginManifestBefore) {
        throw "STOP: P5-02T changed installed plugin manifest."
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $EditCanary).Hash -ne $EditCanaryHashBefore) {
        throw "STOP: P5-02T changed the unrelated edit canary."
    }

    foreach ($name in @(
        "ORION_P5_PRODUCTION_RECOVERY_ROOT",
        "ORION_P5_MUTATION_MODE",
        "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
        "ORION_P5_RECOVERY_ROOT"
    )) {
        if (-not [string]::IsNullOrWhiteSpace(
            [Environment]::GetEnvironmentVariable($name, "Process")
        )) {
            throw "STOP: P5-02T leaked a Phase 5 setting into the parent process: $name"
        }
    }

    Write-Host "P5_02T_CONFIG_UNCHANGED=true"
    Write-Host "P5_02T_ENV_UNCHANGED=true"
    Write-Host "P5_02T_INSTALLED_PLUGIN_UNCHANGED=true"
    Write-Host "P5_02T_EDIT_CANARY_UNCHANGED=true"
    Write-Host "P5_02T_PARENT_MUTATION_MODE_ABSENT=true"
    Write-Host "HERMES_MANUAL_OFF=true"

    if ($ChildExit -ne 0) {
        Write-Host "P5_02T_GATE_RESULT=FAIL_PRESERVE_STATE_AND_RECOVERY_EVIDENCE"
        throw "STOP: P5-02T child reported failure. Do not move/restore/delete either path and do not alter recovery records; preserve state for read-only reconciliation."
    }

    if ($SourceStateAfter -ne "absent") {
        throw "STOP: P5-02T child succeeded but source still exists."
    }
    if ($TargetHashAfter -ne $ExpectedSourceHash) {
        throw "STOP: P5-02T child succeeded but target hash differs from frozen source hash."
    }
    if ($RecoveryCountAfter -ne 3) {
        throw "STOP: P5-02T child succeeded but production recovery count is not exactly 3."
    }

    Write-Host "P5_02T_PARENT_SOURCE_ABSENT=true"
    Write-Host "P5_02T_PARENT_TARGET_HASH_MATCH=true"
    Write-Host "P5_02T_PARENT_RECOVERY_COUNT_MATCH=true"
    Write-Host "P5_02T_GATE_RESULT=PASS"
}
finally {
    if (Test-Path -LiteralPath $SourceWorktree) {
        & git -C $Repo worktree remove --force $SourceWorktree | Out-Null
    }
}
