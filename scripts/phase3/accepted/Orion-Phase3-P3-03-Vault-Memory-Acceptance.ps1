$ErrorActionPreference = "Stop"

$MemoryContainer = "orion-iai-vault-watch"
$VaultContainer = "orion-vault-retrieval"
$VaultRoot = "C:\Personal\Me"
$ResolverScript = "E:\Orion-Phase2\Orion-Phase3-P3-02B-Exact-Vault-Resolver.ps1"
$ProbePayload = "CmltcG9ydCBqc29uCmZyb20gaWFpX21jcC5pYWlfY2xpIGltcG9ydCBfb3Blbl9zdG9yZV9zaGFyZWQsIF9yZWxheV9ycGMKCnN0b3JlID0gX29wZW5fc3RvcmVfc2hhcmVkKCkKdHJ5OgogICAgcmVjb3JkcyA9IHN0b3JlLmFsbF9yZWNvcmRzKCkKZmluYWxseToKICAgIHRyeToKICAgICAgICBzdG9yZS5jbG9zZSgpCiAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgIHBhc3MKCmJ5X3NvdXJjZSA9IHt9CmZvciByZWMgaW4gcmVjb3JkczoKICAgIHN1cmZhY2UgPSAocmVjLmxpdGVyYWxfc3VyZmFjZSBvciAiIikuc3RyaXAoKQogICAgaWYgbGVuKHN1cmZhY2UpIDwgMTIwOgogICAgICAgIGNvbnRpbnVlCiAgICBwcm92cyA9IFtwIGZvciBwIGluIChyZWMucHJvdmVuYW5jZSBvciBbXSkgaWYgaXNpbnN0YW5jZShwLCBkaWN0KV0KICAgIGlmIG5vdCBhbnkocC5nZXQoInNlc3Npb25faWQiKSA9PSAidmF1bHQtc3R1ZHkiIGZvciBwIGluIHByb3ZzKToKICAgICAgICBjb250aW51ZQogICAgc3R1ZHkgPSBbcCBmb3IgcCBpbiBwcm92cyBpZiBwLmdldCgic291cmNlIikgPT0gInN0dWR5IiBhbmQgcC5nZXQoImZpbGVuYW1lIildCiAgICBpZiBub3Qgc3R1ZHk6CiAgICAgICAgY29udGludWUKICAgIHNvdXJjZSA9IHN0cihzdHVkeVswXVsiZmlsZW5hbWUiXSkKICAgIGlmIG5vdCBzb3VyY2UubG93ZXIoKS5lbmRzd2l0aCgiLm1kIik6CiAgICAgICAgY29udGludWUKICAgIGJ5X3NvdXJjZS5zZXRkZWZhdWx0KHNvdXJjZSwgcmVjKQoKc291cmNlcyA9IHNvcnRlZChieV9zb3VyY2UsIGtleT1sYW1iZGEgczogcy5jYXNlZm9sZCgpKQppZiBsZW4oc291cmNlcykgPCAzOgogICAgcHJpbnQoanNvbi5kdW1wcyh7InN0YXR1cyI6ImVycm9yIiwiZXJyb3IiOiJmZXdlcl90aGFuX3RocmVlX3ZhdWx0X3NvdXJjZXMiLCJzb3VyY2VfY291bnQiOmxlbihzb3VyY2VzKX0pKQogICAgcmFpc2UgU3lzdGVtRXhpdCgzMSkKCiMgU3ByZWFkIHByb2JlcyBhY3Jvc3MgdGhlIGNvcnB1cyBpbnN0ZWFkIG9mIHRha2luZyB0aHJlZSBhZGphY2VudCBmaWxlbmFtZXMuCmlkeHMgPSBzb3J0ZWQoc2V0KFswLCBsZW4oc291cmNlcykvLzIsIGxlbihzb3VyY2VzKS0xXSkpCndoaWxlIGxlbihpZHhzKSA8IDM6CiAgICBmb3IgaSBpbiByYW5nZShsZW4oc291cmNlcykpOgogICAgICAgIGlmIGkgbm90IGluIGlkeHM6CiAgICAgICAgICAgIGlkeHMuYXBwZW5kKGkpCiAgICAgICAgICAgIGlmIGxlbihpZHhzKSA9PSAzOgogICAgICAgICAgICAgICAgYnJlYWsKCnJlc3VsdHMgPSBbXQpmb3IgaSBpbiBpZHhzWzozXToKICAgIHNvdXJjZSA9IHNvdXJjZXNbaV0KICAgIHJlYyA9IGJ5X3NvdXJjZVtzb3VyY2VdCiAgICBjdWUgPSAocmVjLmxpdGVyYWxfc3VyZmFjZSBvciAiIikuc3RyaXAoKVs6MzAwXQogICAgcmVzcCA9IF9yZWxheV9ycGMoCiAgICAgICAgIm1lbW9yeV9yZWNhbGwiLAogICAgICAgIHsiY3VlIjogY3VlLCAiYnVkZ2V0X3Rva2VucyI6IDE4MDB9LAogICAgICAgIHRpbWVvdXQ9MzAuMCwKICAgICkKICAgIGlmIG5vdCBpc2luc3RhbmNlKHJlc3AsIGRpY3QpIG9yIHJlc3AuZ2V0KCJzdGF0dXMiKSBpbiAoImRhZW1vbl9kb3duIiwgImVycm9yIik6CiAgICAgICAgcmVzdWx0cy5hcHBlbmQoewogICAgICAgICAgICAic291cmNlX3BhdGgiOiBzb3VyY2UsCiAgICAgICAgICAgICJyZWNvcmRfaWQiOiBzdHIocmVjLmlkKSwKICAgICAgICAgICAgInJwY19vayI6IEZhbHNlLAogICAgICAgICAgICAidGFyZ2V0X2ZvdW5kIjogRmFsc2UsCiAgICAgICAgICAgICJoaXRfY291bnQiOiAwLAogICAgICAgIH0pCiAgICAgICAgY29udGludWUKCiAgICBoaXRzID0gcmVzcC5nZXQoImhpdHMiKSBvciBbXQogICAgaWRzID0gewogICAgICAgIHN0cihoLmdldCgicmVjb3JkX2lkIikgb3IgaC5nZXQoImlkIikgb3IgIiIpCiAgICAgICAgZm9yIGggaW4gaGl0cwogICAgICAgIGlmIGlzaW5zdGFuY2UoaCwgZGljdCkKICAgIH0KICAgIHJlc3VsdHMuYXBwZW5kKHsKICAgICAgICAic291cmNlX3BhdGgiOiBzb3VyY2UsCiAgICAgICAgInJlY29yZF9pZCI6IHN0cihyZWMuaWQpLAogICAgICAgICJycGNfb2siOiBUcnVlLAogICAgICAgICJ0YXJnZXRfZm91bmQiOiBzdHIocmVjLmlkKSBpbiBpZHMsCiAgICAgICAgImhpdF9jb3VudCI6IGxlbihoaXRzKSwKICAgIH0pCgpvayA9IGxlbihyZXN1bHRzKSA9PSAzIGFuZCBhbGwoclsicnBjX29rIl0gYW5kIHJbInRhcmdldF9mb3VuZCJdIGZvciByIGluIHJlc3VsdHMpCnByaW50KGpzb24uZHVtcHMoeyJzdGF0dXMiOiJvayIgaWYgb2sgZWxzZSAiZmFpbCIsInByb2JlX2NvdW50IjpsZW4ocmVzdWx0cyksInByb2JlcyI6cmVzdWx0c30pKQpyYWlzZSBTeXN0ZW1FeGl0KDAgaWYgb2sgZWxzZSAzMikK"
$LifecyclePayload = "CmltcG9ydCBqc29uLCBvcwpmcm9tIGlhaV9tY3AuaWFpX2NsaSBpbXBvcnQgX29wZW5fc3RvcmVfc2hhcmVkCgpzb3VyY2UgPSAob3MuZW52aXJvbi5nZXQoIk9SSU9OX0xJRkVDWUNMRV9TT1VSQ0UiKSBvciAiIikuc3RyaXAoKQp0b2tlbiA9IChvcy5lbnZpcm9uLmdldCgiT1JJT05fTElGRUNZQ0xFX1RPS0VOIikgb3IgIiIpLnN0cmlwKCkKbW9kZSA9IChvcy5lbnZpcm9uLmdldCgiT1JJT05fTElGRUNZQ0xFX01PREUiKSBvciAicHJlc2VudCIpLnN0cmlwKCkKCnN0b3JlID0gX29wZW5fc3RvcmVfc2hhcmVkKCkKdHJ5OgogICAgcmVjb3JkcyA9IHN0b3JlLmFsbF9yZWNvcmRzKCkKZmluYWxseToKICAgIHRyeToKICAgICAgICBzdG9yZS5jbG9zZSgpCiAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgIHBhc3MKCm1hdGNoaW5nID0gW10KZm9yIHJlYyBpbiByZWNvcmRzOgogICAgc3VyZmFjZSA9IHJlYy5saXRlcmFsX3N1cmZhY2Ugb3IgIiIKICAgIGlmIHRva2VuIG5vdCBpbiBzdXJmYWNlOgogICAgICAgIGNvbnRpbnVlCiAgICBwcm92cyA9IFtwIGZvciBwIGluIChyZWMucHJvdmVuYW5jZSBvciBbXSkgaWYgaXNpbnN0YW5jZShwLCBkaWN0KV0KICAgIGhhc19zZXNzaW9uID0gYW55KHAuZ2V0KCJzZXNzaW9uX2lkIikgPT0gInZhdWx0LXN0dWR5IiBmb3IgcCBpbiBwcm92cykKICAgIGhhc19zb3VyY2UgPSBhbnkocC5nZXQoInNvdXJjZSIpID09ICJzdHVkeSIgYW5kIHN0cihwLmdldCgiZmlsZW5hbWUiKSBvciAiIikgPT0gc291cmNlIGZvciBwIGluIHByb3ZzKQogICAgaWYgbm90IChoYXNfc2Vzc2lvbiBhbmQgaGFzX3NvdXJjZSk6CiAgICAgICAgY29udGludWUKICAgIHN1cGVyc2VkZWQgPSBhbnkocC5nZXQoImN1ZSIpID09ICJyZXN0dWR5LXN1cGVyc2VkZSIgZm9yIHAgaW4gcHJvdnMpCiAgICBtYXRjaGluZy5hcHBlbmQoeyJpZCI6c3RyKHJlYy5pZCksInN1cGVyc2VkZWQiOnN1cGVyc2VkZWR9KQoKaWYgbW9kZSA9PSAicHJlc2VudCI6CiAgICBwYXNzZWQgPSBsZW4obWF0Y2hpbmcpID4gMAplbGlmIG1vZGUgPT0gInN1cGVyc2VkZWQiOgogICAgcGFzc2VkID0gYW55KG1bInN1cGVyc2VkZWQiXSBmb3IgbSBpbiBtYXRjaGluZykKZWxzZToKICAgIHByaW50KGpzb24uZHVtcHMoeyJzdGF0dXMiOiJlcnJvciIsImVycm9yIjoiaW52YWxpZF9tb2RlIn0pKQogICAgcmFpc2UgU3lzdGVtRXhpdCg0MSkKCnByaW50KGpzb24uZHVtcHMoewogICAgInN0YXR1cyI6Im9rIiBpZiBwYXNzZWQgZWxzZSAicGVuZGluZyIsCiAgICAibW9kZSI6bW9kZSwKICAgICJzb3VyY2VfcGF0aCI6c291cmNlLAogICAgIm1hdGNoaW5nX3JlY29yZHMiOmxlbihtYXRjaGluZyksCiAgICAic3VwZXJzZWRlZF9yZWNvcmRzIjpzdW0oMSBmb3IgbSBpbiBtYXRjaGluZyBpZiBtWyJzdXBlcnNlZGVkIl0pLAp9KSkKcmFpc2UgU3lzdGVtRXhpdCgwIGlmIHBhc3NlZCBlbHNlIDQyKQo="
$TimeoutSeconds = 120

function To-Text {
    param([object]$Value)
    if ($null -eq $Value) { return "" }
    if ($Value -is [System.Array]) {
        return (($Value | ForEach-Object { [string]$_ }) -join "`n").Trim()
    }
    return ([string]$Value).Trim()
}

function Invoke-DockerJson {
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

    if ([string]::IsNullOrWhiteSpace($text)) {
        return [pscustomobject]@{ ExitCode = $code; Object = $null; Text = $text }
    }

    try {
        $obj = $text | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        if ($AllowFailure) {
            return [pscustomobject]@{ ExitCode = $code; Object = $null; Text = $text }
        }
        throw ("Expected JSON but received: {0}" -f $text)
    }

    return [pscustomobject]@{ ExitCode = $code; Object = $obj; Text = $text }
}

function Invoke-LifecycleProbe {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Token,
        [Parameter(Mandatory = $true)][ValidateSet("present","superseded")][string]$Mode
    )

    $loader = "import base64; exec(base64.b64decode('$LifecyclePayload'))"
    return Invoke-DockerJson -AllowFailure -Args @(
        "exec",
        "-u", "10000:10000",
        "-e", "HOME=/opt/data/profiles/companion",
        "-e", "IAI_MCP_STORE=/opt/data/profiles/companion/.iai-mcp",
        "-e", "IAI_DAEMON_SOCKET_PATH=/opt/data/profiles/companion/.iai-mcp/.daemon.sock",
        "-e", ("ORION_LIFECYCLE_SOURCE={0}" -f $Source),
        "-e", ("ORION_LIFECYCLE_TOKEN={0}" -f $Token),
        "-e", ("ORION_LIFECYCLE_MODE={0}" -f $Mode),
        $MemoryContainer,
        "/opt/iai/venv/bin/python", "-c", $loader
    )
}

function Wait-LifecycleState {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Token,
        [Parameter(Mandatory = $true)][ValidateSet("present","superseded")][string]$Mode,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $attempt = 0
    while ((Get-Date) -lt $deadline) {
        $attempt++
        $probe = Invoke-LifecycleProbe -Source $Source -Token $Token -Mode $Mode
        if ($probe.ExitCode -eq 0 -and $null -ne $probe.Object -and $probe.Object.status -eq "ok") {
            Write-Host ("{0}=PASS" -f $Label)
            Write-Host ("{0}_MATCHING_RECORDS={1}" -f $Label, $probe.Object.matching_records)
            Write-Host ("{0}_SUPERSEDED_RECORDS={1}" -f $Label, $probe.Object.superseded_records)
            return
        }
        if (($attempt % 2) -eq 0) {
            Write-Host ("Waiting for native iai watch: {0} (attempt {1})..." -f $Label, $attempt)
        }
        Start-Sleep -Seconds 5
    }
    throw ("Timed out waiting for {0} after {1} seconds." -f $Label, $TimeoutSeconds)
}

Write-Host "P3-03 Vault-memory acceptance set"
Write-Host "Stages:"
Write-Host "  1. Three representative native iai recall -> exact Obsidian source probes."
Write-Host "  2. One disposable vault note to prove native watch create/change/delete lifecycle."
Write-Host ""
Write-Host "The lifecycle note is temporary and is deleted automatically."
Write-Host "Existing vault notes are not modified."
Write-Host ""

$running = @(& docker ps --format "{{.Names}}")
if ($LASTEXITCODE -ne 0) {
    throw "Could not list Docker containers."
}
if ($running -notcontains $MemoryContainer) {
    throw "'$MemoryContainer' is not running."
}
if ($running -notcontains $VaultContainer) {
    throw "'$VaultContainer' is not running."
}
if (-not (Test-Path -LiteralPath $ResolverScript -PathType Leaf)) {
    throw "Reusable P3-02B resolver not found at '$ResolverScript'."
}
if (-not (Test-Path -LiteralPath $VaultRoot -PathType Container)) {
    throw "Vault root '$VaultRoot' not found."
}
Write-Host "P3_03_PREFLIGHT=PASS"

# ------------------------------------------------------------
# A. Three representative recall -> exact source path probes
# ------------------------------------------------------------
$probeLoader = "import base64; exec(base64.b64decode('$ProbePayload'))"
$probeSet = Invoke-DockerJson -Args @(
    "exec",
    "-u", "10000:10000",
    "-e", "HOME=/opt/data/profiles/companion",
    "-e", "IAI_MCP_STORE=/opt/data/profiles/companion/.iai-mcp",
    "-e", "IAI_DAEMON_SOCKET_PATH=/opt/data/profiles/companion/.iai-mcp/.daemon.sock",
    $MemoryContainer,
    "/opt/iai/venv/bin/python", "-c", $probeLoader
)

if ($probeSet.Object.status -ne "ok" -or [int]$probeSet.Object.probe_count -ne 3) {
    throw ("Native iai representative recall set failed: {0}" -f $probeSet.Text)
}

$probeIndex = 0
foreach ($probe in @($probeSet.Object.probes)) {
    $probeIndex++
    if (-not [bool]$probe.target_found) {
        throw ("Probe {0} did not recall its taught target record." -f $probeIndex)
    }

    $resolverRaw = & powershell.exe `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File $ResolverScript `
        -RecordId ([string]$probe.record_id) `
        -Json 2>&1

    $resolverCode = $LASTEXITCODE
    $resolverText = To-Text $resolverRaw
    if ($resolverCode -ne 0) {
        throw ("P3-02B resolver failed for probe {0}: {1}" -f $probeIndex, $resolverText)
    }

    try {
        $resolved = $resolverText | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw ("P3-02B resolver returned non-JSON for probe {0}: {1}" -f $probeIndex, $resolverText)
    }

    if ($resolved.status -ne "ok") {
        throw ("Resolver returned non-ok for probe {0}." -f $probeIndex)
    }
    if ([string]$resolved.source_path -ne [string]$probe.source_path) {
        throw ("Probe {0} source mismatch: iai='{1}' resolver='{2}'" -f $probeIndex, $probe.source_path, $resolved.source_path)
    }
    if (-not (Test-Path -LiteralPath ([string]$resolved.host_path) -PathType Leaf)) {
        throw ("Probe {0} authoritative host path does not exist: {1}" -f $probeIndex, $resolved.host_path)
    }

    Write-Host ("P3_03_RECALL_PROBE_{0}=PASS" -f $probeIndex)
    Write-Host ("P3_03_RECALL_PROBE_{0}_HITS={1}" -f $probeIndex, $probe.hit_count)
    Write-Host ("P3_03_RECALL_PROBE_{0}_SOURCE={1}" -f $probeIndex, $probe.source_path)
}

Write-Host "P3_03_REPRESENTATIVE_RECALL_SET=PASS"

# ------------------------------------------------------------
# B. Native iai watch lifecycle with one disposable note
# ------------------------------------------------------------
$shortId = [Guid]::NewGuid().ToString("N").Substring(0, 10)
$relativeTestPath = "_orion-p3-03-acceptance-$shortId.md"
$hostTestPath = Join-Path -Path $VaultRoot -ChildPath $relativeTestPath

if (Test-Path -LiteralPath $hostTestPath) {
    throw "Disposable acceptance path unexpectedly already exists: $hostTestPath"
}

$alpha = "ORION_P3_03_ALPHA_$shortId"
$beta = "ORION_P3_03_BETA_$shortId"

$alphaText = @"
# Orion P3-03 disposable acceptance note

This temporary note exists only to verify native iai watch behavior.

Acceptance marker: $alpha

The first version states that the calibration object is amber and the reference number is 314159.
This sentence is deliberately specific so the taught chunk is distinct from normal vault material.
"@

$betaText = @"
# Orion P3-03 disposable acceptance note

This temporary note exists only to verify native iai watch behavior.

Acceptance marker: $beta

The revised version states that the calibration object is cobalt and the reference number is 271828.
The earlier amber statement has been intentionally removed so iai must supersede the old studied chunk.
"@

$testFileCreated = $false
try {
    [System.IO.File]::WriteAllText($hostTestPath, $alphaText, [System.Text.UTF8Encoding]::new($false))
    $testFileCreated = $true
    Write-Host "P3_03_DISPOSABLE_NOTE_CREATED=PASS"
    Write-Host "P3_03_DISPOSABLE_NOTE=$relativeTestPath"

    Wait-LifecycleState `
        -Source $relativeTestPath `
        -Token $alpha `
        -Mode "present" `
        -Label "P3_03_NEW_NOTE_STUDIED"

    Start-Sleep -Seconds 2
    [System.IO.File]::WriteAllText($hostTestPath, $betaText, [System.Text.UTF8Encoding]::new($false))
    Write-Host "P3_03_DISPOSABLE_NOTE_CHANGED=PASS"

    Wait-LifecycleState `
        -Source $relativeTestPath `
        -Token $beta `
        -Mode "present" `
        -Label "P3_03_CHANGED_NOTE_RESTUDIED"

    Wait-LifecycleState `
        -Source $relativeTestPath `
        -Token $alpha `
        -Mode "superseded" `
        -Label "P3_03_OLD_VERSION_SUPERSEDED"

    Remove-Item -LiteralPath $hostTestPath -Force
    $testFileCreated = $false
    Write-Host "P3_03_DISPOSABLE_NOTE_DELETED=PASS"

    Wait-LifecycleState `
        -Source $relativeTestPath `
        -Token $beta `
        -Mode "superseded" `
        -Label "P3_03_DELETED_NOTE_FADE_HINT"

    if (Test-Path -LiteralPath $hostTestPath) {
        throw "Disposable acceptance note still exists after deletion."
    }
    Write-Host "P3_03_DISPOSABLE_NOTE_CLEANUP=PASS"
}
finally {
    if ($testFileCreated -and (Test-Path -LiteralPath $hostTestPath)) {
        Remove-Item -LiteralPath $hostTestPath -Force -ErrorAction SilentlyContinue
        Write-Host "P3_03_FAILSAFE_FILE_CLEANUP=PASS"
    }
}

Write-Host ""
Write-Host "P3_03_NATIVE_WATCH_LIFECYCLE=PASS"
Write-Host "P3_03_VAULT_MEMORY_ACCEPTANCE_SET=PASS"
Write-Host "P3_03_ACCEPTANCE=PASS"
