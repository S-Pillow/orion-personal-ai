$ErrorActionPreference = "Stop"

$MemoryContainer = "orion-iai-m5-c"
$WatchContainer = "orion-iai-vault-watch"
$HostVault = "C:\Personal\Me"
$VaultDestination = "/workspace"
$StoreRoot = "/opt/data/profiles/companion/.iai-mcp"
$ProbeB64 = "CmZyb20gcGF0aGxpYiBpbXBvcnQgUGF0aAppbXBvcnQgc3RhdApmcm9tIGlhaV9tY3AuaWFpX2NsaSBpbXBvcnQgX3JlbGF5X3JwYwoKdmF1bHQgPSBQYXRoKCIvd29ya3NwYWNlIikKc3RvcmUgPSBQYXRoKCIvb3B0L2RhdGEvcHJvZmlsZXMvY29tcGFuaW9uLy5pYWktbWNwIikKc29jayA9IHN0b3JlIC8gIi5kYWVtb24uc29jayIKCmlmIG5vdCB2YXVsdC5pc19kaXIoKToKICAgIHByaW50KCJQM18wMl9WQVVMVF9WSVNJQkxFPUZBSUwiKQogICAgcmFpc2UgU3lzdGVtRXhpdCgxMSkKCm1kX2NvdW50ID0gc3VtKDEgZm9yIHAgaW4gdmF1bHQucmdsb2IoIioubWQiKSBpZiBwLmlzX2ZpbGUoKSBhbmQgbm90IHAuaXNfc3ltbGluaygpKQpwcmludChmIlAzXzAyX1ZBVUxUX01BUktET1dOX0ZJTEVTPXttZF9jb3VudH0iKQppZiBtZF9jb3VudCA8IDE6CiAgICBwcmludCgiUDNfMDJfVkFVTFRfVklTSUJMRT1GQUlMIikKICAgIHJhaXNlIFN5c3RlbUV4aXQoMTIpCnByaW50KCJQM18wMl9WQVVMVF9WSVNJQkxFPVBBU1MiKQoKdHJ5OgogICAgaXNfc29jayA9IHN0YXQuU19JU1NPQ0soc29jay5zdGF0KCkuc3RfbW9kZSkKZXhjZXB0IE9TRXJyb3I6CiAgICBpc19zb2NrID0gRmFsc2UKCnByaW50KGYiUDNfMDJfREFFTU9OX1NPQ0tFVF9WSVNJQkxFPXsnUEFTUycgaWYgaXNfc29jayBlbHNlICdGQUlMJ30iKQppZiBub3QgaXNfc29jazoKICAgIHJhaXNlIFN5c3RlbUV4aXQoMTMpCgpyZXNwID0gX3JlbGF5X3JwYygic3RhdHVzX2xpZ2h0Iiwge30sIHRpbWVvdXQ9MTAuMCkKaWYgbm90IGlzaW5zdGFuY2UocmVzcCwgZGljdCkgb3IgcmVzcC5nZXQoInN0YXR1cyIpIGluICgiZGFlbW9uX2Rvd24iLCAiZXJyb3IiKToKICAgIHByaW50KCJQM18wMl9EQUVNT05fUkVMQVk9RkFJTCIpCiAgICByYWlzZSBTeXN0ZW1FeGl0KDE0KQoKcHJpbnQoIlAzXzAyX0RBRU1PTl9SRUxBWT1QQVNTIikKcHJpbnQoIlAzXzAyX05BVElWRV9XQVRDSF9QUkVGTElHSFQ9UEFTUyIpCg=="

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
    return [pscustomobject]@{ ExitCode = $code; Text = $text }
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

Write-Host "Phase 3 P3-02A: native iai vault learning"
Write-Host "This uses iai's own watch path for new/changed/deleted vault files."
Write-Host ""

if (-not (Test-Path -LiteralPath $HostVault -PathType Container)) {
    throw "Host vault '$HostVault' does not exist."
}
Write-Host "HOST_VAULT_EXISTS=PASS"

$names = Get-ContainerNames
if ($names -notcontains $MemoryContainer) {
    throw "Accepted memory container '$MemoryContainer' was not found."
}

$memory = Get-InspectObject -Name $MemoryContainer
if ($memory.State.Running -ne $true) {
    throw "Accepted memory container '$MemoryContainer' is not running."
}
Write-Host "MEMORY_CONTAINER_RUNNING=PASS"

$doctor = Invoke-Docker -Args @(
    "exec", "-u", "10000:10000", $MemoryContainer, "sh", "-c",
    'HOME=/opt/data/profiles/companion IAI_DAEMON_SOCKET_PATH=/opt/data/profiles/companion/.iai-mcp/.daemon.sock /opt/iai/venv/bin/iai-mcp doctor'
) -AllowFailure

if ($doctor.ExitCode -ne 0 -or $doctor.Text -notmatch "All checks passed") {
    Write-Host "MEMORY_RUNTIME_HEALTH=FAIL"
    Write-Host $doctor.Text
    throw "iai is not healthy. No vault-learning container was created."
}
Write-Host "MEMORY_RUNTIME_HEALTH=PASS"

$imageId = [string]$memory.Image
$dataMounts = @($memory.Mounts | Where-Object { $_.Destination -eq "/opt/data" })
if ($dataMounts.Count -ne 1 -or $dataMounts[0].Type -ne "volume") {
    throw "Could not resolve the accepted /opt/data volume."
}
$dataVolume = [string]$dataMounts[0].Name
if ([string]::IsNullOrWhiteSpace($imageId) -or [string]::IsNullOrWhiteSpace($dataVolume)) {
    throw "Could not resolve accepted image/data-volume identity."
}

Write-Host "IAI_IMAGE_ID=$imageId"
Write-Host "IAI_DATA_VOLUME=$dataVolume"

$probeLoader = "import base64; exec(base64.b64decode('$ProbeB64'))"
$probe = Invoke-Docker -Args @(
    "run", "--rm",
    "--user", "10000:10000",
    "--network", "none",
    "--read-only",
    "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges:true",
    "-e", "HOME=/opt/data/profiles/companion",
    "-e", "IAI_MCP_STORE=$StoreRoot",
    "-e", "IAI_DAEMON_SOCKET_PATH=$StoreRoot/.daemon.sock",
    "-e", "PYTHONDONTWRITEBYTECODE=1",
    "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
    "--mount", ("type=volume,src={0},dst=/opt/data" -f $dataVolume),
    "--mount", ("type=bind,src={0},dst={1},readonly" -f $HostVault, $VaultDestination),
    "--entrypoint", "/opt/iai/venv/bin/python",
    $imageId,
    "-c", $probeLoader
)
Write-Host $probe.Text

if ($probe.Text -notmatch "P3_02_NATIVE_WATCH_PREFLIGHT=PASS") {
    throw "Native iai vault-watch preflight did not pass."
}

$names = Get-ContainerNames
if ($names -contains $WatchContainer) {
    $existing = Get-InspectObject -Name $WatchContainer
    $existingVault = @($existing.Mounts | Where-Object { $_.Destination -eq $VaultDestination })
    $existingData = @($existing.Mounts | Where-Object { $_.Destination -eq "/opt/data" })
    if (
        $existingVault.Count -ne 1 -or
        $existingVault[0].RW -eq $true -or
        $existingData.Count -ne 1 -or
        [string]$existingData[0].Name -ne $dataVolume -or
        [string]$existing.HostConfig.NetworkMode -ne "none"
    ) {
        throw "Existing '$WatchContainer' does not match the approved topology."
    }
    if ($existing.State.Running -ne $true) {
        Invoke-Docker -Args @("start", $WatchContainer) | Out-Null
        Start-Sleep -Seconds 2
    }
    Write-Host "IAI_VAULT_WATCH_CONTAINER=ALREADY_CONFIGURED"
}
else {
    $runArgs = @(
        "run", "-d",
        "--name", $WatchContainer,
        "--restart", "unless-stopped",
        "--user", "10000:10000",
        "--network", "none",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true",
        "-e", "HOME=/opt/data/profiles/companion",
        "-e", "IAI_MCP_STORE=$StoreRoot",
        "-e", "IAI_DAEMON_SOCKET_PATH=$StoreRoot/.daemon.sock",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-e", "PYTHONUNBUFFERED=1",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        "--mount", ("type=volume,src={0},dst=/opt/data" -f $dataVolume),
        "--mount", ("type=bind,src={0},dst={1},readonly" -f $HostVault, $VaultDestination),
        "--entrypoint", "/opt/iai/venv/bin/iai",
        $imageId,
        "watch", $VaultDestination,
        "--interval", "30",
        "--session-id", "vault-study"
    )
    $created = Invoke-Docker -Args $runArgs
    if ([string]::IsNullOrWhiteSpace($created.Text)) {
        throw "Docker did not return a vault-watch container ID."
    }
    Write-Host "IAI_VAULT_WATCH_CONTAINER_CREATED=PASS"
    Start-Sleep -Seconds 3
}

$watch = Get-InspectObject -Name $WatchContainer
if ($watch.State.Running -ne $true) {
    $logs = Invoke-Docker -Args @("logs", "--tail", "80", $WatchContainer) -AllowFailure
    Write-Host $logs.Text
    throw "Vault-watch container is not running."
}

$watchVault = @($watch.Mounts | Where-Object { $_.Destination -eq $VaultDestination })
$watchData = @($watch.Mounts | Where-Object { $_.Destination -eq "/opt/data" })

if ($watchVault.Count -ne 1 -or $watchVault[0].RW -eq $true) {
    throw "Vault-watch safety check failed: /workspace is not read-only."
}
if ($watchData.Count -ne 1 -or [string]$watchData[0].Name -ne $dataVolume) {
    throw "Vault-watch safety check failed: wrong iai data volume."
}
if ([string]$watch.HostConfig.NetworkMode -ne "none") {
    throw "Vault-watch safety check failed: network mode is not none."
}

Write-Host "IAI_VAULT_WATCH_RUNNING=PASS"
Write-Host "IAI_VAULT_WATCH_VAULT_READ_ONLY=PASS"
Write-Host "IAI_VAULT_WATCH_SHARED_STORE=PASS"
Write-Host "IAI_VAULT_WATCH_NETWORK_NONE=PASS"

$logs = Invoke-Docker -Args @("logs", "--tail", "40", $WatchContainer) -AllowFailure
if (-not [string]::IsNullOrWhiteSpace($logs.Text)) {
    Write-Host ""
    Write-Host "Recent native iai watch output:"
    Write-Host $logs.Text
}

Write-Host ""
Write-Host "P3_02A_NATIVE_IAI_VAULT_WATCH=PASS"
Write-Host "WATCH_CONTAINER=$WatchContainer"
Write-Host "WATCH_INTERVAL_SECONDS=30"
Write-Host "WATCH_SESSION_ID=vault-study"
Write-Host "INITIAL_VAULT_STUDY=IN_PROGRESS_OR_COMPLETE"
Write-Host ""
Write-Host "Monitor with:"
Write-Host "  docker logs -f $WatchContainer"
