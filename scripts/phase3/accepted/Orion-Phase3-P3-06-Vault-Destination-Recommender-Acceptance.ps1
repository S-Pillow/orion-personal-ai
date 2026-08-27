$ErrorActionPreference = "Stop"

$InboxRoot = "C:\Personal\Orion-Inbox"
$VaultRoot = "C:\Personal\Me"
$MemoryContainer = "orion-iai-vault-watch"
$DraftCreator = "E:\Orion-Phase2\Orion-Phase3-P3-04-Create-Inbox-Draft.ps1"
$Recommender = "E:\Orion-Phase2\Orion-Phase3-P3-06-Vault-Destination-Recommender.ps1"
$SelectorPayload = "CmltcG9ydCBiYXNlNjQKaW1wb3J0IGpzb24KZnJvbSBwYXRobGliIGltcG9ydCBQdXJlUG9zaXhQYXRoCmZyb20gaWFpX21jcC5pYWlfY2xpIGltcG9ydCBfb3Blbl9zdG9yZV9zaGFyZWQKCnN0b3JlID0gX29wZW5fc3RvcmVfc2hhcmVkKCkKdHJ5OgogICAgcmVjb3JkcyA9IHN0b3JlLmFsbF9yZWNvcmRzKCkKZmluYWxseToKICAgIHRyeToKICAgICAgICBzdG9yZS5jbG9zZSgpCiAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgIHBhc3MKCnNlbGVjdGVkID0gTm9uZQpmb3IgcmVjIGluIHJlY29yZHM6CiAgICBzdXJmYWNlID0gKHJlYy5saXRlcmFsX3N1cmZhY2Ugb3IgIiIpLnN0cmlwKCkKICAgIGlmIGxlbihzdXJmYWNlKSA8IDE2MDoKICAgICAgICBjb250aW51ZQoKICAgIHByb3ZzID0gW3AgZm9yIHAgaW4gKHJlYy5wcm92ZW5hbmNlIG9yIFtdKSBpZiBpc2luc3RhbmNlKHAsIGRpY3QpXQogICAgaWYgbm90IGFueShwLmdldCgic2Vzc2lvbl9pZCIpID09ICJ2YXVsdC1zdHVkeSIgZm9yIHAgaW4gcHJvdnMpOgogICAgICAgIGNvbnRpbnVlCgogICAgc3R1ZHkgPSBbCiAgICAgICAgcCBmb3IgcCBpbiBwcm92cwogICAgICAgIGlmIHAuZ2V0KCJzb3VyY2UiKSA9PSAic3R1ZHkiIGFuZCBwLmdldCgiZmlsZW5hbWUiKQogICAgXQogICAgaWYgbm90IHN0dWR5OgogICAgICAgIGNvbnRpbnVlCgogICAgc291cmNlID0gc3RyKHN0dWR5WzBdWyJmaWxlbmFtZSJdKS5yZXBsYWNlKCJcXCIsICIvIikuc3RyaXAoIi8iKQogICAgaWYgbm90IHNvdXJjZS5sb3dlcigpLmVuZHN3aXRoKCIubWQiKToKICAgICAgICBjb250aW51ZQoKICAgIHBhcmVudCA9IFB1cmVQb3NpeFBhdGgoc291cmNlKS5wYXJlbnQuYXNfcG9zaXgoKQogICAgaWYgcGFyZW50IGluICgiIiwgIi4iKToKICAgICAgICBjb250aW51ZQoKICAgIHNlbGVjdGVkID0gewogICAgICAgICJyZWNvcmRfaWQiOiBzdHIocmVjLmlkKSwKICAgICAgICAic291cmNlX3BhdGgiOiBzb3VyY2UsCiAgICAgICAgImV4cGVjdGVkX2RpcmVjdG9yeSI6IHBhcmVudCwKICAgICAgICAiY3VlX2I2NCI6IGJhc2U2NC5iNjRlbmNvZGUoc3VyZmFjZVs6MjUwMF0uZW5jb2RlKCJ1dGYtOCIpKS5kZWNvZGUoImFzY2lpIiksCiAgICB9CiAgICBicmVhawoKaWYgc2VsZWN0ZWQgaXMgTm9uZToKICAgIHByaW50KGpzb24uZHVtcHMoeyJzdGF0dXMiOiJlcnJvciIsImVycm9yIjoibm9fbm9ucm9vdF92YXVsdF9zdHVkeV9yZWNvcmQifSkpCiAgICByYWlzZSBTeXN0ZW1FeGl0KDIxKQoKcHJpbnQoanNvbi5kdW1wcyh7InN0YXR1cyI6Im9rIiwgKipzZWxlY3RlZH0sIGVuc3VyZV9hc2NpaT1GYWxzZSkpCnJhaXNlIFN5c3RlbUV4aXQoMCkK"

function Get-Sha256File {
    param([Parameter(Mandatory = $true)][string]$Path)

    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            $hash = $sha.ComputeHash($stream)
        }
        finally {
            $sha.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }

    return ([BitConverter]::ToString($hash)).Replace("-", "").ToLowerInvariant()
}

Write-Host "P3-06 Vault destination recommendation acceptance"
Write-Host "This is read-only against the authoritative vault."
Write-Host "It creates and removes one disposable inbox draft only."
Write-Host ""

foreach ($path in @($InboxRoot, $VaultRoot)) {
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        throw "Required directory not found: $path"
    }
}
foreach ($scriptPath in @($DraftCreator, $Recommender)) {
    if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) {
        throw "Required operational script not found: $scriptPath"
    }
}

$running = @(& docker ps --format "{{.Names}}")
if ($LASTEXITCODE -ne 0 -or $running -notcontains $MemoryContainer) {
    throw "Native iai vault-watch container is not running."
}
Write-Host "P3_06_PREFLIGHT=PASS"

# Select one existing non-root taught vault record without printing its content.
$selectorLoader = "import base64; exec(base64.b64decode('$SelectorPayload'))"
$selectedRaw = & docker exec `
    -u 10000:10000 `
    -e "HOME=/opt/data/profiles/companion" `
    -e "IAI_MCP_STORE=/opt/data/profiles/companion/.iai-mcp" `
    -e "IAI_DAEMON_SOCKET_PATH=/opt/data/profiles/companion/.iai-mcp/.daemon.sock" `
    $MemoryContainer `
    /opt/iai/venv/bin/python -c $selectorLoader 2>&1

if ($LASTEXITCODE -ne 0) {
    throw ("Could not select acceptance source: {0}" -f (($selectedRaw | ForEach-Object { [string]$_ }) -join "`n"))
}

$selectedText = (($selectedRaw | ForEach-Object { [string]$_ }) -join "`n").Trim()
try {
    $selected = $selectedText | ConvertFrom-Json -ErrorAction Stop
}
catch {
    throw ("Acceptance selector returned non-JSON: {0}" -f $selectedText)
}

if ($selected.status -ne "ok") {
    throw "Acceptance selector returned non-ok status."
}

$expectedDir = [string]$selected.expected_directory
$expectedHostDir = Join-Path -Path $VaultRoot -ChildPath ($expectedDir -replace "/", "\")
if (-not (Test-Path -LiteralPath $expectedHostDir -PathType Container)) {
    throw "Selected taught source directory is not present in the authoritative vault."
}
Write-Host "P3_06_ACCEPTANCE_SOURCE_SELECTED=PASS"
Write-Host ("P3_06_EXPECTED_DIRECTORY={0}" -f $expectedDir)

try {
    $cueBytes = [Convert]::FromBase64String([string]$selected.cue_b64)
    $cueText = [System.Text.Encoding]::UTF8.GetString($cueBytes)
}
catch {
    throw "Could not decode the local acceptance cue."
}

$shortId = [Guid]::NewGuid().ToString("N").Substring(0, 10)
$draftName = ("orion-p3-06-destination-{0}.md" -f $shortId)
$draftHost = Join-Path -Path $InboxRoot -ChildPath $draftName

try {
    $createRaw = & powershell.exe `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File $DraftCreator `
        -Title "P3-06 Destination Acceptance" `
        -Body $cueText `
        -Filename $draftName `
        -Json 2>&1

    if ($LASTEXITCODE -ne 0) {
        throw ("Could not create disposable acceptance draft: {0}" -f (($createRaw | ForEach-Object { [string]$_ }) -join "`n"))
    }
    if (-not (Test-Path -LiteralPath $draftHost -PathType Leaf)) {
        throw "Disposable inbox draft was not created."
    }
    Write-Host "P3_06_DISPOSABLE_DRAFT_CREATED=PASS"

    $draftBefore = Get-Sha256File -Path $draftHost

    $recRaw = & powershell.exe `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File $Recommender `
        -DraftFile $draftName `
        -Top 5 `
        -Json 2>&1

    if ($LASTEXITCODE -ne 0) {
        throw ("Destination recommender failed: {0}" -f (($recRaw | ForEach-Object { [string]$_ }) -join "`n"))
    }

    $recText = (($recRaw | ForEach-Object { [string]$_ }) -join "`n").Trim()
    try {
        $result = $recText | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw ("Destination recommender returned non-JSON: {0}" -f $recText)
    }

    if ($result.status -ne "ok") {
        throw "Destination recommender returned non-ok status."
    }
    if ([int]$result.recommendation_count -lt 1) {
        throw "Destination recommender returned no current vault directory candidates."
    }

    $dirs = @($result.recommendations | ForEach-Object { [string]$_.directory })
    if ($dirs -notcontains $expectedDir) {
        throw ("Expected directory '{0}' was not among the recommendations: {1}" -f $expectedDir, ($dirs -join ", "))
    }
    Write-Host "P3_06_EXPECTED_DIRECTORY_RECOMMENDED=PASS"

    foreach ($item in @($result.recommendations)) {
        $dir = [string]$item.directory
        $hostDir = if ([string]::IsNullOrWhiteSpace($dir)) {
            $VaultRoot
        }
        else {
            Join-Path -Path $VaultRoot -ChildPath ($dir -replace "/", "\")
        }
        if (-not (Test-Path -LiteralPath $hostDir -PathType Container)) {
            throw ("Recommendation points to a non-existent authoritative directory: {0}" -f $dir)
        }
    }
    Write-Host "P3_06_RECOMMENDATIONS_EXIST_IN_VAULT=PASS"

    $draftAfter = Get-Sha256File -Path $draftHost
    if ($draftAfter -ne $draftBefore) {
        throw "Read-only recommendation changed the inbox draft."
    }
    Write-Host "P3_06_RECOMMENDER_NO_DRAFT_WRITE=PASS"
    Write-Host "P3_06_NATIVE_IAI_DESTINATION_RECOMMENDATION=PASS"
}
finally {
    if (Test-Path -LiteralPath $draftHost) {
        Remove-Item -LiteralPath $draftHost -Force -ErrorAction SilentlyContinue
    }
}

if (Test-Path -LiteralPath $draftHost) {
    throw "Disposable P3-06 draft cleanup failed."
}
Write-Host "P3_06_DISPOSABLE_CLEANUP=PASS"

Write-Host ""
Write-Host "P3_06_VAULT_DESTINATION_RECOMMENDER=PASS"
Write-Host "P3_06_ACCEPTANCE=PASS"
