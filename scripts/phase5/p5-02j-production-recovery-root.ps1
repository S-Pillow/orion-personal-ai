param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("I_AUTHORIZE_P5_02J_PRODUCTION_RECOVERY_ROOT")]
    [string]$AuthorizationToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# P5-02J creates exactly one production recovery directory and protects only
# that directory's ACL. It does not persist any Orion environment setting,
# start Hermes, enable mutation mode, register a production executor, or touch
# real vault/inbox contents.

$Hermes = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent\venv\Scripts\hermes.exe"
$HermesPython = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent\venv\Scripts\python.exe"
$Profile = Join-Path $env:LOCALAPPDATA "hermes\profiles\companion"
$Config = Join-Path $Profile "config.yaml"
$EnvFile = Join-Path $Profile ".env"
$PluginDest = Join-Path $Profile "plugins\orion-vault-actions"
$OrionStateParent = Join-Path $Profile "orion"
$CandidateRoot = Join-Path $OrionStateParent "production-recovery"
$Verifier = Join-Path $PSScriptRoot "p5-02j-verify-production-recovery-root.py"

$ExpectedConfigHash = "34D9BD9DDC1BC59783CE2DC80D98FBD66D7AA7CC670DDFB875E0D1C78E8462D7"
$ExpectedPluginInitHash = "FCFA3DDC4A86B99691FB003CF4421027C5CC3CA22AC99ADBCCEEE8D3B3C7B5DA"

$ForbiddenPersistentOrProcess = @(
    "ORION_P5_MUTATION_MODE",
    "ORION_P5_PRODUCTION_RECOVERY_ROOT",
    "ORION_P5_ALLOW_DISPOSABLE_MUTATION",
    "ORION_P5_RECOVERY_ROOT"
)

function Get-OptionalFileHash {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
}

function Test-GatewayHealth {
    $uri = "http" + "://127.0.0.1:8642/health"
    try {
        $null = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 2
        return $true
    }
    catch {
        return $false
    }
}

function Assert-NoReparseComponent {
    param([Parameter(Mandatory = $true)][string]$ExistingPath)

    $item = Get-Item -LiteralPath $ExistingPath -Force
    while ($null -ne $item) {
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "STOP: reparse component rejected: $($item.FullName)"
        }
        $item = $item.Parent
    }
}

function Assert-ExpectedAcl {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.SecurityIdentifier]$CurrentSid
    )

    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $expected = @(
        $CurrentSid.Value,
        $systemSid.Value,
        $adminsSid.Value
    )

    $acl = Get-Acl -LiteralPath $Path
    if (-not $acl.AreAccessRulesProtected) {
        throw "STOP: production recovery ACL inheritance is not protected."
    }

    $ownerSid = ([System.Security.Principal.NTAccount]$acl.Owner).Translate(
        [System.Security.Principal.SecurityIdentifier]
    )
    if ($ownerSid.Value -ne $CurrentSid.Value) {
        throw "STOP: production recovery root owner is not the current operator."
    }

    $rules = @(
        $acl.GetAccessRules(
            $true,
            $true,
            [System.Security.Principal.SecurityIdentifier]
        )
    )

    if ($rules.Count -ne 3) {
        throw "STOP: unexpected number of production recovery ACL entries: $($rules.Count)"
    }

    foreach ($rule in $rules) {
        if ($rule.IsInherited) {
            throw "STOP: inherited ACL entry remains on production recovery root."
        }
        if ($rule.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow) {
            throw "STOP: unexpected non-Allow ACL entry on production recovery root."
        }

        $sid = $rule.IdentityReference.Value
        if ($expected -notcontains $sid) {
            throw "STOP: unexpected ACL principal on production recovery root: $sid"
        }

        $full = [System.Security.AccessControl.FileSystemRights]::FullControl
        if (($rule.FileSystemRights -band $full) -ne $full) {
            throw "STOP: expected FullControl missing for production recovery principal: $sid"
        }
    }

    foreach ($sid in $expected) {
        if (-not ($rules.IdentityReference.Value -contains $sid)) {
            throw "STOP: required ACL principal missing: $sid"
        }
    }

    Write-Host "P5_02J_ACL_INHERITANCE_PROTECTED=true"
    Write-Host "P5_02J_ACL_EXPECTED_PRINCIPALS_ONLY=true"
    Write-Host "P5_02J_OWNER_SID=$($CurrentSid.Value)"
}

if ($AuthorizationToken -ne "I_AUTHORIZE_P5_02J_PRODUCTION_RECOVERY_ROOT") {
    throw "STOP: explicit P5-02J authorization token required."
}

if (-not (Test-Path -LiteralPath $Hermes -PathType Leaf)) {
    throw "STOP: Hermes executable missing."
}
if (-not (Test-Path -LiteralPath $HermesPython -PathType Leaf)) {
    throw "STOP: Hermes Python missing."
}
if (-not (Test-Path -LiteralPath $Config -PathType Leaf)) {
    throw "STOP: COMPANION config missing."
}
if (-not (Test-Path -LiteralPath $PluginDest -PathType Container)) {
    throw "STOP: installed Orion plugin missing."
}
if (-not (Test-Path -LiteralPath $Verifier -PathType Leaf)) {
    throw "STOP: P5-02J verifier missing."
}
if (-not (Test-Path -LiteralPath $OrionStateParent -PathType Container)) {
    throw "STOP: existing COMPANION Orion state parent is missing."
}

Assert-NoReparseComponent -ExistingPath $OrionStateParent

if (Test-Path -LiteralPath $CandidateRoot) {
    throw "STOP: proposed production recovery root already exists: $CandidateRoot"
}

$ConfigBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash
if ($ConfigBefore -ne $ExpectedConfigHash) {
    throw "STOP: COMPANION config hash differs from accepted baseline."
}

$PluginInit = Join-Path $PluginDest "__init__.py"
$PluginHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $PluginInit).Hash
if ($PluginHash -ne $ExpectedPluginInitHash) {
    throw "STOP: installed Orion plugin hash differs from accepted P5-02I baseline."
}

$EnvBeforePresent = Test-Path -LiteralPath $EnvFile -PathType Leaf
$EnvBeforeHash = if ($EnvBeforePresent) {
    Get-OptionalFileHash -Path $EnvFile
}
else {
    $null
}

foreach ($name in $ForbiddenPersistentOrProcess) {
    $processValue = [Environment]::GetEnvironmentVariable($name, "Process")
    if (-not [string]::IsNullOrWhiteSpace($processValue)) {
        throw "STOP: unexpected process setting present: $name"
    }

    if (
        $EnvBeforePresent -and
        (Select-String -LiteralPath $EnvFile -Pattern ("^\s*" + [regex]::Escape($name) + "\s*=") -Quiet)
    ) {
        throw "STOP: persistent COMPANION setting already present: $name"
    }
}

& $Hermes -p companion gateway status
if (Test-GatewayHealth) {
    throw "STOP: Hermes gateway is running; P5-02J requires manual-off."
}

$currentIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$currentSid = $currentIdentity.User
if ($null -eq $currentSid) {
    throw "STOP: current Windows SID unavailable."
}

$CreatedRoot = $false
$Passed = $false

try {
    New-Item -ItemType Directory -Path $CandidateRoot -ErrorAction Stop | Out-Null
    $CreatedRoot = $true

    # Replace inheritance on the newly created directory only.
    $acl = Get-Acl -LiteralPath $CandidateRoot
    $acl.SetAccessRuleProtection($true, $false)

    # Remove any remaining explicit entries before adding the exact accepted set.
    foreach ($rule in @($acl.Access)) {
        if (-not $rule.IsInherited) {
            $null = $acl.RemoveAccessRuleSpecific($rule)
        }
    }

    $acl.SetOwner($currentSid)

    $inheritance = (
        [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
        [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    )
    $propagation = [System.Security.AccessControl.PropagationFlags]::None
    $allow = [System.Security.AccessControl.AccessControlType]::Allow
    $fullControl = [System.Security.AccessControl.FileSystemRights]::FullControl

    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")

    foreach ($sid in @($currentSid, $systemSid, $adminsSid)) {
        $accessRule = [System.Security.AccessControl.FileSystemAccessRule]::new(
            $sid,
            $fullControl,
            $inheritance,
            $propagation,
            $allow
        )
        $null = $acl.AddAccessRule($accessRule)
    }

    Set-Acl -LiteralPath $CandidateRoot -AclObject $acl

    Assert-ExpectedAcl -Path $CandidateRoot -CurrentSid $currentSid

    Write-Host "P5_02J_ROOT=$CandidateRoot"
    Write-Host "P5_02J_ROOT_CREATED=true"

    # Native installed-plugin validation. The verifier process-scopes the
    # recovery root and keeps production mutation mode absent/disabled.
    & $HermesPython $Verifier $PluginDest $CandidateRoot
    if ($LASTEXITCODE -ne 0) {
        throw "STOP: native P5-02J recovery-root validation failed."
    }

    # Persistent files must be byte-for-byte unchanged.
    $ConfigAfter = (Get-FileHash -Algorithm SHA256 -LiteralPath $Config).Hash
    if ($ConfigAfter -ne $ConfigBefore) {
        throw "STOP: COMPANION config changed during P5-02J."
    }

    $EnvAfterPresent = Test-Path -LiteralPath $EnvFile -PathType Leaf
    if ($EnvAfterPresent -ne $EnvBeforePresent) {
        throw "STOP: COMPANION .env presence changed during P5-02J."
    }
    if ($EnvAfterPresent) {
        $EnvAfterHash = Get-OptionalFileHash -Path $EnvFile
        if ($EnvAfterHash -ne $EnvBeforeHash) {
            throw "STOP: COMPANION .env changed during P5-02J."
        }
    }

    foreach ($name in $ForbiddenPersistentOrProcess) {
        $processValue = [Environment]::GetEnvironmentVariable($name, "Process")
        if (-not [string]::IsNullOrWhiteSpace($processValue)) {
            throw "STOP: process mutation setting persisted unexpectedly: $name"
        }
    }

    if (Test-GatewayHealth) {
        throw "STOP: Hermes gateway unexpectedly started during P5-02J."
    }

    Write-Host "P5_02J_CONFIG_UNCHANGED=true"
    Write-Host "P5_02J_ENV_UNCHANGED=true"
    Write-Host "HERMES_MANUAL_OFF=true"
    Write-Host "P5_02J_PRODUCTION_RECOVERY_ROOT_ACCEPTANCE=PASS"

    $Passed = $true
}
catch {
    Write-Host ""
    Write-Host "P5-02J FAILED."
    Write-Host "Candidate root: $CandidateRoot"

    if ($CreatedRoot -and (Test-Path -LiteralPath $CandidateRoot -PathType Container)) {
        $children = @(Get-ChildItem -LiteralPath $CandidateRoot -Force)
        if ($children.Count -eq 0) {
            Remove-Item -LiteralPath $CandidateRoot -Force
            Write-Host "P5_02J_EMPTY_CREATED_ROOT_ROLLED_BACK=true"
        }
        else {
            Write-Host "P5_02J_CREATED_ROOT_PRESERVED_NONEMPTY=true"
        }
    }

    throw
}
finally {
    if (-not $Passed) {
        Write-Host "P5_02J_PRODUCTION_RECOVERY_ROOT_ACCEPTANCE=FAIL"
    }
}
