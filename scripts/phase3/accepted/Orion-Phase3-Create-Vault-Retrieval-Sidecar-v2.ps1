$ErrorActionPreference = "Stop"

$MemoryContainer = "orion-iai-m5-c"
$VaultContainer = "orion-vault-retrieval"
$HostVault = "C:\Personal\Me"
$VaultDestination = "/workspace"

function To-Text {
    param([object]$Value)
    if ($null -eq $Value) { return "" }
    if ($Value -is [System.Array]) {
        return (($Value | ForEach-Object { [string]$_ }) -join "`n").Trim()
    }
    return ([string]$Value).Trim()
}

function Invoke-Docker {
    param(
        [Parameter(Mandatory = $true)][string[]]$Args,
        [switch]$AllowFailure
    )

    $raw = & docker @Args 2>&1
    $code = $LASTEXITCODE
    $text = To-Text $raw

    if (-not $AllowFailure -and $code -ne 0) {
        throw ("docker {0} failed (exit {1}): {2}" -f ($Args -join " "), $code, $text)
    }

    return [pscustomobject]@{
        ExitCode = $code
        Text = $text
    }
}

function Get-ContainerNames {
    $r = Invoke-Docker -Args @("ps", "-a", "--format", "{{.Names}}")
    if ([string]::IsNullOrWhiteSpace($r.Text)) { return @() }
    return @($r.Text -split "`r?`n")
}

function Get-InspectObject {
    param([Parameter(Mandatory = $true)][string]$Name)

    $r = Invoke-Docker -Args @("inspect", $Name)
    $obj = $r.Text | ConvertFrom-Json -ErrorAction Stop
    if ($null -eq $obj -or $obj.Count -lt 1) {
        throw "docker inspect returned no data for '$Name'."
    }
    return $obj[0]
}

Write-Host "Phase 3 vault retrieval sidecar setup v2"
Write-Host "The accepted iai/Hermes container remains untouched."
Write-Host "The vault sidecar gets a read-only vault, no network, and ephemeral tmpfs at /opt/data."
Write-Host ""

if (-not (Test-Path -LiteralPath $HostVault -PathType Container)) {
    throw "Host vault '$HostVault' does not exist."
}
Write-Host "HOST_VAULT_EXISTS=PASS"

$names = Get-ContainerNames
if ($names -notcontains $MemoryContainer) {
    throw "Accepted Orion memory container '$MemoryContainer' was not found."
}

$memory = Get-InspectObject -Name $MemoryContainer
if ($memory.State.Running -ne $true) {
    throw "Accepted Orion memory container '$MemoryContainer' is not running."
}
Write-Host "MEMORY_CONTAINER_RUNNING=PASS"

# Confirm the accepted memory runtime is healthy before changing only the sidecar.
$doctor = Invoke-Docker -Args @(
    "exec",
    "-u", "10000:10000",
    $MemoryContainer,
    "sh", "-c",
    'HOME=/opt/data/profiles/companion IAI_DAEMON_SOCKET_PATH=/opt/data/profiles/companion/.iai-mcp/.daemon.sock /opt/iai/venv/bin/iai-mcp doctor'
) -AllowFailure

if ($doctor.ExitCode -ne 0 -or $doctor.Text -notmatch "All checks passed") {
    Write-Host "MEMORY_RUNTIME_HEALTH=FAIL"
    Write-Host $doctor.Text
    throw "Accepted iai runtime is not healthy. No sidecar changes were made."
}
Write-Host "MEMORY_RUNTIME_HEALTH=PASS"

$imageId = [string]$memory.Image
if ([string]::IsNullOrWhiteSpace($imageId)) {
    throw "Could not resolve the exact accepted Orion image ID."
}

$memoryDataMounts = @($memory.Mounts | Where-Object { $_.Destination -eq "/opt/data" })
if ($memoryDataMounts.Count -ne 1) {
    throw "Expected exactly one /opt/data mount on the accepted memory container."
}
$memoryData = $memoryDataMounts[0]

Write-Host "SIDECAR_IMAGE_ID=$imageId"
Write-Host "MEMORY_DATA_MOUNT_TYPE=$($memoryData.Type)"
Write-Host "MEMORY_DATA_MOUNT_SOURCE=$($memoryData.Source)"

# Clean up only the failed/stateless Phase 3 sidecar from the previous attempt.
$names = Get-ContainerNames
if ($names -contains $VaultContainer) {
    $oldSidecar = Get-InspectObject -Name $VaultContainer

    $dangerous = @(
        $oldSidecar.Mounts |
        Where-Object {
            ($_.Destination -eq "/opt/data") -and
            (
                ($_.Source -eq $memoryData.Source) -or
                (
                    -not [string]::IsNullOrWhiteSpace([string]$memoryData.Name) -and
                    $_.Name -eq $memoryData.Name
                )
            )
        }
    )

    if ($dangerous.Count -gt 0) {
        throw "Refusing sidecar cleanup: existing sidecar shares the accepted memory data mount."
    }

    Write-Host "OLD_SIDECAR_MEMORY_VOLUME_SHARED=NO"
    Write-Host "Removing previous stateless vault sidecar and its anonymous volumes..."
    Invoke-Docker -Args @("rm", "-f", "-v", $VaultContainer) | Out-Null
    Write-Host "OLD_SIDECAR_REMOVED=PASS"
}

# Explicit tmpfs at /opt/data overrides any image-declared VOLUME at that path.
# This guarantees the retrieval sidecar cannot see or persist COMPANION iai data.
$runArgs = @(
    "run",
    "-d",
    "--name", $VaultContainer,
    "--restart", "unless-stopped",
    "--user", "10000:10000",
    "--network", "none",
    "--read-only",
    "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges:true",
    "-e", "HOME=/tmp",
    "-e", "PYTHONDONTWRITEBYTECODE=1",
    "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
    "--tmpfs", "/opt/data:rw,noexec,nosuid,size=8m",
    "--mount", ("type=bind,src={0},dst={1},readonly" -f $HostVault, $VaultDestination),
    "--entrypoint", "/opt/iai/venv/bin/python",
    $imageId,
    "-c", "import time; time.sleep(315360000)"
)

$started = Invoke-Docker -Args $runArgs
if ([string]::IsNullOrWhiteSpace($started.Text)) {
    throw "Docker did not return a sidecar container ID."
}
Write-Host "VAULT_SIDECAR_STARTED=PASS"

$sidecar = Get-InspectObject -Name $VaultContainer
if ($sidecar.State.Running -ne $true) {
    throw "Vault sidecar exited during startup."
}

$workspaceMounts = @($sidecar.Mounts | Where-Object { $_.Destination -eq $VaultDestination })
if ($workspaceMounts.Count -ne 1) {
    throw "Expected exactly one /workspace mount on the vault sidecar; found $($workspaceMounts.Count)."
}
if ($workspaceMounts[0].RW -eq $true) {
    throw "Safety failure: vault sidecar /workspace mount is writable."
}
Write-Host "VAULT_MOUNT_READ_ONLY=PASS"

if ([string]$sidecar.HostConfig.NetworkMode -ne "none") {
    throw "Isolation failure: vault sidecar has network access."
}
Write-Host "VAULT_SIDECAR_NETWORK_NONE=PASS"

# Docker reports tmpfs in HostConfig.Tmpfs rather than Mounts on some engines,
# so verify from both metadata and inside the container.
$tmpfs = $sidecar.HostConfig.Tmpfs
$tmpfsData = $null
if ($null -ne $tmpfs) {
    $tmpfsData = $tmpfs."/opt/data"
}
if ([string]::IsNullOrWhiteSpace([string]$tmpfsData)) {
    throw "Isolation failure: /opt/data is not configured as tmpfs on the vault sidecar."
}
Write-Host "SIDECAR_OPT_DATA_TMPFS=PASS"

$probeCode = @'
from pathlib import Path
import os

root = Path("/workspace")
if not root.is_dir():
    raise SystemExit(11)

count = sum(1 for p in root.rglob("*.md") if p.is_file() and not p.is_symlink())
print(f"VAULT_MARKDOWN_FILES={count}")
if count < 1:
    raise SystemExit(12)

data = Path("/opt/data")
if not data.is_dir():
    raise SystemExit(13)

# The retrieval sidecar must not contain the COMPANION memory store.
live_store = data / "profiles" / "companion" / ".iai-mcp"
print(f"SIDECAR_COMPANION_STORE_PRESENT={'true' if live_store.exists() else 'false'}")
if live_store.exists():
    raise SystemExit(14)

print("VAULT_CORPUS_READ=PASS")
print("SIDECAR_HAS_NO_COMPANION_STORE=PASS")
'@

$probeB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($probeCode))
$loader = "import base64; exec(base64.b64decode('$probeB64'))"

$probe = Invoke-Docker -Args @(
    "exec",
    $VaultContainer,
    "/opt/iai/venv/bin/python",
    "-c", $loader
)

Write-Host $probe.Text

Write-Host ""
Write-Host "PH3_VAULT_SIDECAR=PASS"
Write-Host "VAULT_CONTAINER=$VaultContainer"
Write-Host "VAULT_HOST_PATH=$HostVault"
Write-Host "VAULT_CONTAINER_PATH=$VaultDestination"
Write-Host "VAULT_ACCESS=READ_ONLY"
Write-Host "NETWORK_ACCESS=NONE"
Write-Host "OPT_DATA=EPHEMERAL_TMPFS"
Write-Host "PH3_P3_01=PASS"
