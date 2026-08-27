[CmdletBinding()]
param(
    [switch]$Execute,
    [string]$TagPrefix = "orion-rebuild"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$HermesTag = "${TagPrefix}-hermes-ddgs:v2026.8.18"
$F2Tag = "${TagPrefix}-iai-f2:v3.0.0"
$ArtifactTag = "${TagPrefix}-iai-hf-artifact:bge-small-en-v1.5"
$F5eTag = "${TagPrefix}-iai-f5e:v3.0.0"
$M2Tag = "${TagPrefix}-iai-m2:v3.0.8"
$M4Tag = "${TagPrefix}-combined-m4:v2026.8.18-iai3.0.8"
$M5Tag = "${TagPrefix}-m5:v2026.8.18-iai3.0.8-serializerfix"

function Invoke-Docker {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$AllowFailure
    )

    $saved = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $raw = & docker.exe @Arguments 2>&1
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $saved
    }

    $text = (($raw | ForEach-Object { [string]$_ }) -join "`n").Trim()

    if (($code -ne 0) -and (-not $AllowFailure)) {
        throw ("Docker failed (exit {0}): docker {1}`n{2}" -f $code, ($Arguments -join " "), $text)
    }

    return [pscustomobject]@{
        ExitCode = $code
        Text = $text
    }
}

function Assert-TagAbsent {
    param([Parameter(Mandatory = $true)][string]$Tag)

    $result = Invoke-Docker -AllowFailure -Arguments @("image", "inspect", $Tag)
    if ($result.ExitCode -eq 0) {
        throw ("Target rebuild tag already exists; refusing to overwrite evidence: {0}" -f $Tag)
    }
}

Write-Host "Orion canonical rebuild candidate"
Write-Host ("Root={0}" -f $Root)
Write-Host ("FinalTag={0}" -f $M5Tag)

if (-not $Execute) {
    Write-Host "REBUILD_MODE=PLAN_ONLY"
    Write-Host "REBUILD_DOCKER_MUTATION=NONE"
    Write-Host "REBUILD_PLAN=PASS"
    exit 0
}

if (-not (Get-Command docker.exe -ErrorAction SilentlyContinue)) {
    throw "docker.exe was not found in PATH."
}

foreach ($tag in @($HermesTag, $F2Tag, $ArtifactTag, $F5eTag, $M2Tag, $M4Tag, $M5Tag)) {
    Assert-TagAbsent -Tag $tag
}

Write-Host "REBUILD_TARGET_TAGS_ABSENT=PASS"

Invoke-Docker -Arguments @(
    "build",
    "--file", (Join-Path $Root "Dockerfile.01-hermes-ddgs"),
    "--tag", $HermesTag,
    $Root
) | Out-Null
Write-Host "REBUILD_HERMES_DDGS=PASS"

Invoke-Docker -Arguments @(
    "build",
    "--build-arg", ("HERMES_DDGS_IMAGE={0}" -f $HermesTag),
    "--file", (Join-Path $Root "Dockerfile.02-iai-f2"),
    "--tag", $F2Tag,
    $Root
) | Out-Null
Write-Host "REBUILD_IAI_F2=PASS"

$acquireScript = (Resolve-Path -LiteralPath (Join-Path $Root "acquire_f5e_model.py")).Path
$acquireContainer = "orion-rebuild-f5e-" + ([Guid]::NewGuid().ToString("N").Substring(0, 12))
$acquireCreated = $false

try {
    Invoke-Docker -Arguments @(
        "run",
        "--name", $acquireContainer,
        "--network", "bridge",
        "--dns", "1.1.1.1",
        "--dns", "8.8.8.8",
        "--env", "HF_HOME=/opt/iai/hf",
        "--mount", ("type=bind,source={0},target=/tmp/acquire_f5e_model.py,readonly" -f $acquireScript),
        "--entrypoint", "/opt/iai/venv/bin/python",
        $F2Tag,
        "/tmp/acquire_f5e_model.py"
    ) | Out-Null

    $acquireCreated = $true
    Write-Host "REBUILD_F5E_ACQUISITION=PASS"

    Invoke-Docker -Arguments @("commit", $acquireContainer, $ArtifactTag) | Out-Null
    Write-Host "REBUILD_F5E_ARTIFACT_STAGE=PASS"
}
finally {
    if ($acquireCreated) {
        Invoke-Docker -AllowFailure -Arguments @("rm", $acquireContainer) | Out-Null
    }
}

Invoke-Docker -Arguments @(
    "build",
    "--network", "none",
    "--build-arg", ("IAI_F2_IMAGE={0}" -f $F2Tag),
    "--build-arg", ("HF_ARTIFACT_IMAGE={0}" -f $ArtifactTag),
    "--file", (Join-Path $Root "Dockerfile.03-iai-f5e"),
    "--tag", $F5eTag,
    $Root
) | Out-Null
Write-Host "REBUILD_IAI_F5E=PASS"

Invoke-Docker -Arguments @(
    "build",
    "--build-arg", ("IAI_F5E_IMAGE={0}" -f $F5eTag),
    "--file", (Join-Path $Root "Dockerfile.04-iai-m2"),
    "--tag", $M2Tag,
    $Root
) | Out-Null
Write-Host "REBUILD_IAI_M2=PASS"

Invoke-Docker -Arguments @(
    "build",
    "--network", "none",
    "--build-arg", ("IAI_M2_IMAGE={0}" -f $M2Tag),
    "--build-arg", ("HERMES_DDGS_IMAGE={0}" -f $HermesTag),
    "--file", (Join-Path $Root "Dockerfile.05-combined-m4"),
    "--tag", $M4Tag,
    $Root
) | Out-Null
Write-Host "REBUILD_COMBINED_M4=PASS"

Invoke-Docker -Arguments @(
    "build",
    "--network", "none",
    "--build-arg", ("M4_IMAGE={0}" -f $M4Tag),
    "--file", (Join-Path $Root "Dockerfile.06-m5"),
    "--tag", $M5Tag,
    $Root
) | Out-Null
Write-Host "REBUILD_M5=PASS"

$verifyScript = (Resolve-Path -LiteralPath (Join-Path $Root "verify_final_image.py")).Path

Invoke-Docker -Arguments @(
    "run",
    "--rm",
    "--network", "none",
    "--mount", ("type=bind,source={0},target=/tmp/verify_final_image.py,readonly" -f $verifyScript),
    "--entrypoint", "/opt/iai/venv/bin/python",
    $M5Tag,
    "/tmp/verify_final_image.py"
) | Out-Null

$finalId = (Invoke-Docker -Arguments @("image", "inspect", "--format", "{{.Id}}", $M5Tag)).Text

Write-Host ("REBUILD_FINAL_IMAGE_ID={0}" -f $finalId)
Write-Host ("REBUILD_FINAL_TAG={0}" -f $M5Tag)
Write-Host "REBUILD_ACCEPTED_RUNTIME_MUTATION=NONE"
Write-Host "REBUILD_DISPOSABLE_CHAIN=PASS"
