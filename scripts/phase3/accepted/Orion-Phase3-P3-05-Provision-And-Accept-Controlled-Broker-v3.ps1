$ErrorActionPreference = "Stop"

$VaultHost = "C:\Personal\Me"
$InboxHost = "C:\Personal\Orion-Inbox"
$RecoveryHost = "C:\Personal\Orion-Recovery"
$Container = "orion-vault-broker"
$ImageSourceContainer = "orion-iai-m5-c"
$DraftCreator = "E:\Orion-Phase2\Orion-Phase3-P3-04-Create-Inbox-Draft.ps1"
$Broker = "E:\Orion-Phase2\Orion-Phase3-P3-05-Controlled-Vault-Broker-v2.ps1"

function Invoke-BrokerJson {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$AllowFailure
    )

    $raw = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Broker @Arguments -Json 2>&1
    $code = $LASTEXITCODE
    $text = (($raw | ForEach-Object { [string]$_ }) -join "`n").Trim()

    if ([string]::IsNullOrWhiteSpace($text)) {
        throw "Broker invocation returned no output."
    }

    try {
        $obj = $text | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        if ($AllowFailure) {
            return [pscustomobject]@{ ExitCode = $code; Object = $null; Text = $text }
        }
        throw ("Broker returned non-JSON: {0}" -f $text)
    }

    if (-not $AllowFailure -and $code -ne 0) {
        throw ("Broker invocation failed (exit {0}): {1}" -f $code, $text)
    }

    return [pscustomobject]@{ ExitCode = $code; Object = $obj; Text = $text }
}

function Remove-RecoveryEntry {
    param([string]$RecoveryFile)
    if ([string]::IsNullOrWhiteSpace($RecoveryFile)) { return }
    $parts = ($RecoveryFile -replace "\\","/").Split("/")
    if ($parts.Count -lt 2) { return }
    $entry = Join-Path -Path $RecoveryHost -ChildPath $parts[0]
    if (Test-Path -LiteralPath $entry -PathType Container) {
        Remove-Item -LiteralPath $entry -Recurse -Force
    }
}

Write-Host "P3-05 Controlled edit/move broker acceptance"
Write-Host "This creates only disposable test material."
Write-Host "Existing vault notes are not modified."
Write-Host ""

foreach ($path in @($VaultHost, $InboxHost)) {
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        throw "Required host directory not found: $path"
    }
}
if (-not (Test-Path -LiteralPath $RecoveryHost -PathType Container)) {
    New-Item -ItemType Directory -Path $RecoveryHost -Force | Out-Null
}
if (-not (Test-Path -LiteralPath $DraftCreator -PathType Leaf)) {
    throw "P3-04 draft creator not found at '$DraftCreator'."
}
if (-not (Test-Path -LiteralPath $Broker -PathType Leaf)) {
    throw "P3-05 broker script not found at '$Broker'."
}
Write-Host "P3_05_HOST_PATHS=PASS"

$imageId = (& docker inspect -f "{{.Image}}" $ImageSourceContainer 2>&1 | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($imageId)) {
    throw "Could not resolve accepted image ID."
}
Write-Host ("P3_05_IMAGE_ID={0}" -f $imageId)

$existing = @(& docker ps -a --format "{{.Names}}")
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
    --mount ("type=bind,source={0},target=/workspace" -f $VaultHost) `
    --mount ("type=bind,source={0},target=/inbox" -f $InboxHost) `
    --mount ("type=bind,source={0},target=/recovery" -f $RecoveryHost) `
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
Write-Host "P3_05_BROKER_CONTAINER_RUNNING=PASS"

$inspectRaw = & docker inspect $Container 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Could not inspect broker container."
}
$inspect = ($inspectRaw -join "`n") | ConvertFrom-Json -ErrorAction Stop
$cfg = $inspect[0]
$mounts = @($cfg.Mounts)

foreach ($dest in @("/workspace","/inbox","/recovery")) {
    $m = @($mounts | Where-Object { $_.Destination -eq $dest })
    if ($m.Count -ne 1 -or $m[0].RW -ne $true) {
        throw "Expected one writable bind mount at $dest."
    }
}
Write-Host "P3_05_BROKER_RW_BOUNDARIES=PASS"

$dataPersistent = @($mounts | Where-Object {
    $_.Destination -eq "/opt/data" -and ($_.Type -eq "bind" -or $_.Type -eq "volume")
})
if ($dataPersistent.Count -ne 0) {
    throw "Broker unexpectedly received a persistent /opt/data mount."
}
Write-Host "P3_05_NO_MEMORY_VOLUME=PASS"

$tmpfsNames = @()
if ($null -ne $cfg.HostConfig.Tmpfs) {
    $tmpfsNames = @($cfg.HostConfig.Tmpfs.PSObject.Properties.Name)
}
if ($tmpfsNames -notcontains "/opt/data") {
    throw "Broker /opt/data is not ephemeral tmpfs."
}
Write-Host "P3_05_EPHEMERAL_DATA_TMPFS=PASS"

if ([string]$cfg.HostConfig.NetworkMode -ne "none") {
    throw "Broker network must be none."
}
if ($cfg.HostConfig.ReadonlyRootfs -ne $true) {
    throw "Broker root filesystem must be read-only."
}
if (([string]$cfg.Config.User) -ne "10000:10000") {
    throw "Broker must run as 10000:10000."
}
Write-Host "P3_05_BROKER_HARDENING=PASS"

$shortId = [Guid]::NewGuid().ToString("N").Substring(0, 10)
$draftName = ("orion-p3-05-draft-{0}.md" -f $shortId)
$targetRel = ("artifacts/orion-p3-05-acceptance-{0}.md" -f $shortId)
$draftHost = Join-Path -Path $InboxHost -ChildPath $draftName
$targetHost = Join-Path -Path $VaultHost -ChildPath ($targetRel -replace "/","\")

$moveRecovery = $null
$editRecovery = $null
$restoreRecovery = $null
$targetCreated = $false

try {
    $body = "P3-05 acceptance marker ORIGINAL-$shortId`n`nThis disposable draft verifies approval-gated move and edit behavior."
    $draftRaw = & powershell.exe `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File $DraftCreator `
        -Title "P3-05 Broker Acceptance" `
        -Body $body `
        -Filename $draftName `
        -Json 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ("Could not create disposable inbox draft: {0}" -f (($draftRaw | ForEach-Object { [string]$_ }) -join "`n"))
    }
    if (-not (Test-Path -LiteralPath $draftHost -PathType Leaf)) {
        throw "Disposable inbox draft is not visible on the host."
    }
    Write-Host "P3_05_DISPOSABLE_DRAFT_CREATED=PASS"

    # Move preview must not write.
    $movePreview = Invoke-BrokerJson -Arguments @(
        "-Action","MoveDraft",
        "-Mode","Preview",
        "-SourceDraft",$draftName,
        "-TargetRelativePath",$targetRel
    )
    if ($movePreview.Object.status -ne "ok" -or [string]::IsNullOrWhiteSpace([string]$movePreview.Object.approval_token)) {
        throw "Move preview did not return an approval token."
    }
    if (-not (Test-Path -LiteralPath $draftHost -PathType Leaf) -or (Test-Path -LiteralPath $targetHost)) {
        throw "Move preview changed filesystem state."
    }
    Write-Host "P3_05_MOVE_PREVIEW=PASS"
    Write-Host "P3_05_MOVE_PREVIEW_NO_WRITE=PASS"

    # Wrong approval token = explicit denial/no-op proof.
    $badMove = Invoke-BrokerJson -AllowFailure -Arguments @(
        "-Action","MoveDraft",
        "-Mode","Apply",
        "-SourceDraft",$draftName,
        "-TargetRelativePath",$targetRel,
        "-ApprovalToken","DENIED"
    )
    if ($badMove.ExitCode -ne 20 -or $null -eq $badMove.Object -or $badMove.Object.status -ne "denied") {
        throw ("Move denial contract mismatch. Exit={0}; Output={1}" -f $badMove.ExitCode, $badMove.Text)
    }
    if (-not (Test-Path -LiteralPath $draftHost -PathType Leaf) -or (Test-Path -LiteralPath $targetHost)) {
        throw "Denied move changed filesystem state."
    }
    Write-Host "P3_05_DENIED_MOVE_NOOP=PASS"

    # Approved move.
    $moveApply = Invoke-BrokerJson -Arguments @(
        "-Action","MoveDraft",
        "-Mode","Apply",
        "-SourceDraft",$draftName,
        "-TargetRelativePath",$targetRel,
        "-ApprovalToken",([string]$movePreview.Object.approval_token)
    )
    $moveRecovery = [string]$moveApply.Object.recovery_file
    $targetCreated = $true
    if ((Test-Path -LiteralPath $draftHost) -or -not (Test-Path -LiteralPath $targetHost -PathType Leaf)) {
        throw "Approved move did not produce exact source->target state."
    }
    Write-Host "P3_05_APPROVED_MOVE=PASS"
    Write-Host ("P3_05_MOVE_RECOVERY_FILE={0}" -f $moveRecovery)

    $originalBytes = [System.IO.File]::ReadAllBytes($targetHost)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $originalSha = ([BitConverter]::ToString($sha.ComputeHash($originalBytes))).Replace("-","").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }

    $originalText = [System.IO.File]::ReadAllText($targetHost)
    $editedText = $originalText.Replace("ORIGINAL-$shortId", "EDITED-$shortId")
    if ($editedText -eq $originalText) {
        throw "Could not prepare deterministic edited content."
    }

    # Edit preview.
    $editPreview = Invoke-BrokerJson -Arguments @(
        "-Action","EditNote",
        "-Mode","Preview",
        "-TargetRelativePath",$targetRel,
        "-NewContent",$editedText
    )
    if ($editPreview.Object.status -ne "ok" -or [string]$editPreview.Object.diff -notmatch "EDITED-$shortId") {
        throw "Edit preview did not expose the expected exact diff."
    }
    $beforeDeniedSha = $originalSha
    Write-Host "P3_05_EDIT_PREVIEW_DIFF=PASS"

    # Wrong approval token must leave target unchanged.
    $badEdit = Invoke-BrokerJson -AllowFailure -Arguments @(
        "-Action","EditNote",
        "-Mode","Apply",
        "-TargetRelativePath",$targetRel,
        "-NewContent",$editedText,
        "-ApprovalToken","DENIED"
    )
    if ($badEdit.ExitCode -ne 20 -or $null -eq $badEdit.Object -or $badEdit.Object.status -ne "denied") {
        throw ("Edit denial contract mismatch. Exit={0}; Output={1}" -f $badEdit.ExitCode, $badEdit.Text)
    }
    $afterDeniedBytes = [System.IO.File]::ReadAllBytes($targetHost)
    $sha2 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $afterDeniedSha = ([BitConverter]::ToString($sha2.ComputeHash($afterDeniedBytes))).Replace("-","").ToLowerInvariant()
    }
    finally {
        $sha2.Dispose()
    }
    if ($afterDeniedSha -ne $beforeDeniedSha) {
        throw "Denied edit changed the target."
    }
    Write-Host "P3_05_DENIED_EDIT_NOOP=PASS"

    # Approved edit.
    $editApply = Invoke-BrokerJson -Arguments @(
        "-Action","EditNote",
        "-Mode","Apply",
        "-TargetRelativePath",$targetRel,
        "-NewContent",$editedText,
        "-ApprovalToken",([string]$editPreview.Object.approval_token)
    )
    $editRecovery = [string]$editApply.Object.recovery_file
    $postEdit = [System.IO.File]::ReadAllText($targetHost)
    if ($postEdit -notmatch "EDITED-$shortId" -or $postEdit -match "ORIGINAL-$shortId") {
        throw "Approved edit result is not exact."
    }
    if ([string]::IsNullOrWhiteSpace($editRecovery)) {
        throw "Approved edit did not return a recovery file."
    }
    $editRecoveryHost = Join-Path -Path $RecoveryHost -ChildPath ($editRecovery -replace "/","\")
    if (-not (Test-Path -LiteralPath $editRecoveryHost -PathType Leaf)) {
        throw "Approved edit recovery backup is missing."
    }
    Write-Host "P3_05_APPROVED_EDIT_EXACT=PASS"
    Write-Host "P3_05_EDIT_RECOVERY_BACKUP=PASS"
    Write-Host ("P3_05_EDIT_RECOVERY_FILE={0}" -f $editRecovery)

    # Restore preview + approved restore proves recovery path works.
    $restorePreview = Invoke-BrokerJson -Arguments @(
        "-Action","Restore",
        "-Mode","Preview",
        "-TargetRelativePath",$targetRel,
        "-RecoveryFile",$editRecovery
    )
    if ($restorePreview.Object.status -ne "ok") {
        throw "Restore preview failed."
    }
    Write-Host "P3_05_RESTORE_PREVIEW=PASS"

    $restoreApply = Invoke-BrokerJson -Arguments @(
        "-Action","Restore",
        "-Mode","Apply",
        "-TargetRelativePath",$targetRel,
        "-RecoveryFile",$editRecovery,
        "-ApprovalToken",([string]$restorePreview.Object.approval_token)
    )
    $restoreRecovery = [string]$restoreApply.Object.recovery_file

    $restoredBytes = [System.IO.File]::ReadAllBytes($targetHost)
    $sha3 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $restoredSha = ([BitConverter]::ToString($sha3.ComputeHash($restoredBytes))).Replace("-","").ToLowerInvariant()
    }
    finally {
        $sha3.Dispose()
    }
    if ($restoredSha -ne $originalSha) {
        throw "Restore did not recover the exact original bytes."
    }
    Write-Host "P3_05_RECOVERY_RESTORE_EXACT=PASS"
}
finally {
    # User-invoked acceptance cleanup: disposable material only.
    if (Test-Path -LiteralPath $draftHost) {
        Remove-Item -LiteralPath $draftHost -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $targetHost) {
        Remove-Item -LiteralPath $targetHost -Force -ErrorAction SilentlyContinue
    }

    foreach ($rf in @($moveRecovery, $editRecovery, $restoreRecovery)) {
        Remove-RecoveryEntry -RecoveryFile $rf
    }

    $artifactDir = Split-Path -Path $targetHost -Parent
    if (Test-Path -LiteralPath $artifactDir -PathType Container) {
        $remaining = @(Get-ChildItem -LiteralPath $artifactDir -Force -ErrorAction SilentlyContinue)
        if ($remaining.Count -eq 0) {
            Remove-Item -LiteralPath $artifactDir -Force -ErrorAction SilentlyContinue
        }
    }
}

if ((Test-Path -LiteralPath $draftHost) -or (Test-Path -LiteralPath $targetHost)) {
    throw "Disposable acceptance cleanup did not fully complete."
}
Write-Host "P3_05_DISPOSABLE_CLEANUP=PASS"

Write-Host ""
Write-Host ("P3_05_BROKER_CONTAINER={0}" -f $Container)
Write-Host ("P3_05_RECOVERY_HOST={0}" -f $RecoveryHost)
Write-Host "P3_05_CONTROLLED_EDIT_MOVE_BROKER=PASS"
Write-Host "P3_05_ACCEPTANCE=PASS"
