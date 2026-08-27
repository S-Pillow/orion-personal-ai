$ErrorActionPreference = "Stop"

$InboxHost = "C:\Personal\Orion-Inbox"
$VaultHost = "C:\Personal\Me"
$Container = "orion-inbox-writer"
$ImageSourceContainer = "orion-iai-m5-c"
$DraftCreator = "E:\Orion-Phase2\Orion-Phase3-P3-04-Create-Inbox-Draft.ps1"

Write-Host "P3-04 Dedicated Orion inbox"
Write-Host "Creates a bounded writable inbox outside the authoritative Obsidian vault."
Write-Host "The inbox writer receives no /workspace vault mount and no iai memory volume."
Write-Host ""

if (-not (Test-Path -LiteralPath $VaultHost -PathType Container)) {
    throw "Authoritative vault not found at '$VaultHost'."
}
if (-not (Test-Path -LiteralPath $DraftCreator -PathType Leaf)) {
    throw "Reusable draft creator not found at '$DraftCreator'."
}

if (-not (Test-Path -LiteralPath $InboxHost -PathType Container)) {
    New-Item -ItemType Directory -Path $InboxHost -Force | Out-Null
}
Write-Host "P3_04_INBOX_HOST_EXISTS=PASS"

# Ensure the inbox is outside the authoritative vault tree.
$vaultFull = [System.IO.Path]::GetFullPath($VaultHost).TrimEnd('\')
$inboxFull = [System.IO.Path]::GetFullPath($InboxHost).TrimEnd('\')
if ($inboxFull.StartsWith($vaultFull + "\", [System.StringComparison]::OrdinalIgnoreCase) -or
    $inboxFull.Equals($vaultFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Inbox must be outside the authoritative vault tree."
}
Write-Host "P3_04_INBOX_OUTSIDE_VAULT=PASS"

$imageId = (& docker inspect -f "{{.Image}}" $ImageSourceContainer 2>&1 | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($imageId)) {
    throw "Could not resolve accepted image ID from '$ImageSourceContainer'."
}
Write-Host ("P3_04_IMAGE_ID={0}" -f $imageId)

$existing = @(& docker ps -a --format "{{.Names}}")
if ($LASTEXITCODE -ne 0) {
    throw "Could not list Docker containers."
}

if ($existing -contains $Container) {
    & docker rm -f -v $Container | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not replace existing '$Container'."
    }
}

& docker create `
    --name $Container `
    --restart unless-stopped `
    --user "10000:10000" `
    --network none `
    --read-only `
    --cap-drop ALL `
    --security-opt no-new-privileges `
    --mount ("type=bind,source={0},target=/inbox" -f $InboxHost) `
    --tmpfs "/opt/data:rw,noexec,nosuid,size=64m" `
    --tmpfs "/tmp:rw,noexec,nosuid,size=64m" `
    --entrypoint /bin/sh `
    $imageId `
    -c "sleep infinity" | Out-Null

if ($LASTEXITCODE -ne 0) {
    throw "Could not create '$Container'."
}

& docker start $Container | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Could not start '$Container'."
}

$running = @(& docker ps --format "{{.Names}}")
if ($running -notcontains $Container) {
    throw "'$Container' is not running."
}
Write-Host "P3_04_INBOX_CONTAINER_RUNNING=PASS"

$inspectRaw = & docker inspect $Container 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Could not inspect '$Container'."
}
$inspect = ($inspectRaw -join "`n") | ConvertFrom-Json -ErrorAction Stop
$cfg = $inspect[0]
$mounts = @($cfg.Mounts)

$inboxMounts = @($mounts | Where-Object { $_.Destination -eq "/inbox" })
if ($inboxMounts.Count -ne 1) {
    throw "Expected exactly one /inbox mount."
}
if ($inboxMounts[0].RW -ne $true) {
    throw "/inbox is not writable."
}
Write-Host "P3_04_INBOX_MOUNT_RW=PASS"

if (@($mounts | Where-Object { $_.Destination -eq "/workspace" }).Count -ne 0) {
    throw "Inbox writer must not receive the authoritative vault mount."
}
Write-Host "P3_04_NO_VAULT_MOUNT=PASS"

$dataMounts = @($mounts | Where-Object { $_.Destination -eq "/opt/data" })
$persistentDataMounts = @($dataMounts | Where-Object { $_.Type -eq "volume" -or $_.Type -eq "bind" })
if ($persistentDataMounts.Count -ne 0) {
    throw "Inbox writer received a persistent /opt/data mount; refusing isolation acceptance."
}

$tmpfsNames = @()
if ($null -ne $cfg.HostConfig.Tmpfs) {
    $tmpfsNames = @($cfg.HostConfig.Tmpfs.PSObject.Properties.Name)
}
if ($tmpfsNames -notcontains "/opt/data") {
    throw "Inbox writer does not have the required ephemeral /opt/data tmpfs."
}
Write-Host "P3_04_NO_MEMORY_VOLUME=PASS"
Write-Host "P3_04_EPHEMERAL_DATA_TMPFS=PASS"

if ([string]$cfg.HostConfig.NetworkMode -ne "none") {
    throw "Inbox writer network mode is not none."
}
Write-Host "P3_04_NETWORK_NONE=PASS"

if ($cfg.HostConfig.ReadonlyRootfs -ne $true) {
    throw "Inbox writer root filesystem is not read-only."
}
Write-Host "P3_04_ROOTFS_READ_ONLY=PASS"

if (([string]$cfg.Config.User) -ne "10000:10000") {
    throw "Inbox writer is not running as UID/GID 10000:10000."
}
Write-Host "P3_04_UID_GID=PASS"

# Prove /inbox is writable and the host directory reflects the write.
$testName = ("orion-p3-04-smoke-{0}.md" -f ([Guid]::NewGuid().ToString("N").Substring(0, 10)))
$testBody = "Temporary P3-04 acceptance draft. This file is removed by the acceptance test."
$draftRaw = & powershell.exe `
    -NoProfile `
    -ExecutionPolicy Bypass `
    -File $DraftCreator `
    -Title "P3-04 Inbox Smoke" `
    -Body $testBody `
    -Filename $testName `
    -Json 2>&1

$draftCode = $LASTEXITCODE
$draftText = (($draftRaw | ForEach-Object { [string]$_ }) -join "`n").Trim()
if ($draftCode -ne 0) {
    throw ("Reusable draft creator smoke failed: {0}" -f $draftText)
}

try {
    $draft = $draftText | ConvertFrom-Json -ErrorAction Stop
}
catch {
    throw ("Reusable draft creator returned non-JSON: {0}" -f $draftText)
}

if ($draft.status -ne "ok") {
    throw "Draft creator returned non-ok status."
}

$hostSmoke = Join-Path -Path $InboxHost -ChildPath $testName
if (-not (Test-Path -LiteralPath $hostSmoke -PathType Leaf)) {
    throw "Draft created in container was not visible on the host inbox."
}
Write-Host "P3_04_DRAFT_CREATE_SMOKE=PASS"

$smokeContent = Get-Content -LiteralPath $hostSmoke -Raw
if ($smokeContent -notmatch "orion_draft:\s*true" -or
    $smokeContent -notmatch "status:\s*draft" -or
    $smokeContent -notmatch "generated_by:\s*Orion") {
    throw "Draft metadata markers are missing."
}
Write-Host "P3_04_DRAFT_METADATA=PASS"

Remove-Item -LiteralPath $hostSmoke -Force
if (Test-Path -LiteralPath $hostSmoke) {
    throw "Acceptance draft cleanup failed."
}
Write-Host "P3_04_ACCEPTANCE_DRAFT_CLEANUP=PASS"

Write-Host ""
Write-Host ("P3_04_INBOX_HOST={0}" -f $InboxHost)
Write-Host ("P3_04_CONTAINER={0}" -f $Container)
Write-Host "P3_04_DEDICATED_ORION_INBOX=PASS"
Write-Host "P3_04_ACCEPTANCE=PASS"
