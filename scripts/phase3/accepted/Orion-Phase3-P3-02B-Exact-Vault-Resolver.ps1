[CmdletBinding(DefaultParameterSetName = "ByRecord")]
param(
    [Parameter(Mandatory = $true, ParameterSetName = "ByRecord")]
    [string]$RecordId,

    [Parameter(Mandatory = $true, ParameterSetName = "BySource")]
    [string]$SourcePath,

    [switch]$Read,

    [ValidateRange(1, 50000)]
    [int]$MaxChars = 12000,

    [switch]$Json
)

$ErrorActionPreference = "Stop"

$MemoryContainer = "orion-iai-vault-watch"
$VaultContainer = "orion-vault-retrieval"
$HostVaultRoot = "C:\Personal\Me"
$LookupPayload = "CmltcG9ydCBqc29uLCBvcwpmcm9tIHV1aWQgaW1wb3J0IFVVSUQKZnJvbSBpYWlfbWNwLmlhaV9jbGkgaW1wb3J0IF9vcGVuX3N0b3JlX3NoYXJlZAoKcmlkID0gKG9zLmVudmlyb24uZ2V0KCJPUklPTl9SRUNPUkRfSUQiKSBvciAiIikuc3RyaXAoKQpvdXQgPSB7InN0YXR1cyI6ICJlcnJvciIsICJyZWNvcmRfaWQiOiByaWR9Cgp0cnk6CiAgICB1aWQgPSBVVUlEKHJpZCkKZXhjZXB0IEV4Y2VwdGlvbjoKICAgIG91dC51cGRhdGUoZXJyb3I9ImludmFsaWRfcmVjb3JkX2lkIikKICAgIHByaW50KGpzb24uZHVtcHMob3V0KSkKICAgIHJhaXNlIFN5c3RlbUV4aXQoMikKCnN0b3JlID0gX29wZW5fc3RvcmVfc2hhcmVkKCkKdHJ5OgogICAgcmVjID0gc3RvcmUuZ2V0KHVpZCkKZmluYWxseToKICAgIHRyeToKICAgICAgICBzdG9yZS5jbG9zZSgpCiAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgIHBhc3MKCmlmIHJlYyBpcyBOb25lOgogICAgb3V0LnVwZGF0ZShlcnJvcj0icmVjb3JkX25vdF9mb3VuZCIpCiAgICBwcmludChqc29uLmR1bXBzKG91dCkpCiAgICByYWlzZSBTeXN0ZW1FeGl0KDMpCgpwcm92cyA9IFtwIGZvciBwIGluIChyZWMucHJvdmVuYW5jZSBvciBbXSkgaWYgaXNpbnN0YW5jZShwLCBkaWN0KV0Kc2Vzc2lvbl9vayA9IGFueShwLmdldCgic2Vzc2lvbl9pZCIpID09ICJ2YXVsdC1zdHVkeSIgZm9yIHAgaW4gcHJvdnMpCnN0dWR5X3Byb3ZzID0gW3AgZm9yIHAgaW4gcHJvdnMgaWYgcC5nZXQoInNvdXJjZSIpID09ICJzdHVkeSJdCmZpbGVuYW1lcyA9IHNvcnRlZCh7CiAgICBzdHIocC5nZXQoImZpbGVuYW1lIikpCiAgICBmb3IgcCBpbiBzdHVkeV9wcm92cwogICAgaWYgcC5nZXQoImZpbGVuYW1lIikKfSkKCmlmIG5vdCBzZXNzaW9uX29rIG9yIG5vdCBmaWxlbmFtZXM6CiAgICBvdXQudXBkYXRlKAogICAgICAgIHN0YXR1cz0ibm90X3ZhdWx0X3N0dWR5IiwKICAgICAgICBlcnJvcj0icmVjb3JkX2hhc19ub192YXVsdF9zdHVkeV9zb3VyY2UiLAogICAgICAgIHNvdXJjZV9wYXRocz1maWxlbmFtZXMsCiAgICApCiAgICBwcmludChqc29uLmR1bXBzKG91dCkpCiAgICByYWlzZSBTeXN0ZW1FeGl0KDQpCgppZiBsZW4oZmlsZW5hbWVzKSAhPSAxOgogICAgb3V0LnVwZGF0ZSgKICAgICAgICBzdGF0dXM9ImFtYmlndW91cyIsCiAgICAgICAgZXJyb3I9InJlY29yZF9oYXNfbXVsdGlwbGVfc291cmNlX3BhdGhzIiwKICAgICAgICBzb3VyY2VfcGF0aHM9ZmlsZW5hbWVzLAogICAgKQogICAgcHJpbnQoanNvbi5kdW1wcyhvdXQpKQogICAgcmFpc2UgU3lzdGVtRXhpdCg1KQoKb3V0ID0gewogICAgInN0YXR1cyI6ICJvayIsCiAgICAicmVjb3JkX2lkIjogcmlkLAogICAgInNvdXJjZV9wYXRoIjogZmlsZW5hbWVzWzBdLAogICAgInNvdXJjZSI6ICJzdHVkeSIsCiAgICAic2Vzc2lvbl9pZCI6ICJ2YXVsdC1zdHVkeSIsCn0KcHJpbnQoanNvbi5kdW1wcyhvdXQpKQo="
$ResolverPayload = "CmltcG9ydCBoYXNobGliLCBqc29uLCBvcywgcmUKZnJvbSBwYXRobGliIGltcG9ydCBQYXRoLCBQdXJlUG9zaXhQYXRoCgpyb290ID0gUGF0aCgiL3dvcmtzcGFjZSIpCnJlcXVlc3RlZCA9IChvcy5lbnZpcm9uLmdldCgiT1JJT05fU09VUkNFX1BBVEgiKSBvciAiIikuc3RyaXAoKQpyZWFkX2NvbnRlbnQgPSAob3MuZW52aXJvbi5nZXQoIk9SSU9OX1JFQURfQ09OVEVOVCIpIG9yICIwIikgPT0gIjEiCgp0cnk6CiAgICBtYXhfY2hhcnMgPSBpbnQob3MuZW52aXJvbi5nZXQoIk9SSU9OX01BWF9DSEFSUyIpIG9yICIxMjAwMCIpCmV4Y2VwdCBFeGNlcHRpb246CiAgICBtYXhfY2hhcnMgPSAxMjAwMAptYXhfY2hhcnMgPSBtYXgoMSwgbWluKG1heF9jaGFycywgNTAwMDApKQoKZGVmIGVtaXQob2JqLCBjb2RlPTApOgogICAgcHJpbnQoanNvbi5kdW1wcyhvYmosIGVuc3VyZV9hc2NpaT1GYWxzZSkpCiAgICByYWlzZSBTeXN0ZW1FeGl0KGNvZGUpCgppZiBub3Qgcm9vdC5pc19kaXIoKToKICAgIGVtaXQoeyJzdGF0dXMiOiJlcnJvciIsImVycm9yIjoidmF1bHRfcm9vdF9taXNzaW5nIn0sIDEwKQoKaWYgbm90IHJlcXVlc3RlZCBvciAiXHgwMCIgaW4gcmVxdWVzdGVkOgogICAgZW1pdCh7InN0YXR1cyI6ImVycm9yIiwiZXJyb3IiOiJpbnZhbGlkX3NvdXJjZV9wYXRoIn0sIDExKQoKbm9ybWFsaXplZCA9IHJlcXVlc3RlZC5yZXBsYWNlKCJcXCIsICIvIikKaWYgbm9ybWFsaXplZC5zdGFydHN3aXRoKCIvIikgb3IgcmUubWF0Y2gociJeW0EtWmEtel06Iiwgbm9ybWFsaXplZCk6CiAgICBlbWl0KHsic3RhdHVzIjoiZXJyb3IiLCJlcnJvciI6ImFic29sdXRlX3BhdGhfcmVqZWN0ZWQiLCJyZXF1ZXN0ZWRfc291cmNlIjpyZXF1ZXN0ZWR9LCAxMikKCnBhcnRzID0gUHVyZVBvc2l4UGF0aChub3JtYWxpemVkKS5wYXJ0cwppZiBub3QgcGFydHMgb3IgYW55KHAgaW4gKCIiLCAiLiIsICIuLiIpIGZvciBwIGluIHBhcnRzKToKICAgIGVtaXQoeyJzdGF0dXMiOiJlcnJvciIsImVycm9yIjoicGF0aF90cmF2ZXJzYWxfcmVqZWN0ZWQiLCJyZXF1ZXN0ZWRfc291cmNlIjpyZXF1ZXN0ZWR9LCAxMykKCnJvb3RfcmVhbCA9IHJvb3QucmVzb2x2ZSgpCmNhbmRpZGF0ZSA9IHJvb3Quam9pbnBhdGgoKnBhcnRzKQoKIyBEbyBub3QgcGVybWl0IHN5bWxpbmsgdHJhdmVyc2FsIGV2ZW4gaWYgdGhlIGZpbmFsIHJlYWwgcGF0aCBzdGF5cyB1bmRlciByb290LgpjdXJzb3IgPSByb290CmZvciBwYXJ0IGluIHBhcnRzOgogICAgY3Vyc29yID0gY3Vyc29yIC8gcGFydAogICAgdHJ5OgogICAgICAgIGlmIGN1cnNvci5pc19zeW1saW5rKCk6CiAgICAgICAgICAgIGVtaXQoeyJzdGF0dXMiOiJlcnJvciIsImVycm9yIjoic3ltbGlua19wYXRoX3JlamVjdGVkIiwicmVxdWVzdGVkX3NvdXJjZSI6cmVxdWVzdGVkfSwgMTQpCiAgICBleGNlcHQgT1NFcnJvcjoKICAgICAgICBwYXNzCgptYXRjaF9tb2RlID0gImV4YWN0LXJlbGF0aXZlIgppZiBub3QgY2FuZGlkYXRlLmlzX2ZpbGUoKToKICAgICMgQSBzaW5nbGUtZmlsZSB0ZWFjaCBtYXkgcHJlc2VydmUgb25seSBhIGJhc2VuYW1lLiBQZXJtaXQgYSBkZXRlcm1pbmlzdGljCiAgICAjIHVuaXF1ZSBjYXNlLWluc2Vuc2l0aXZlIGJhc2VuYW1lIGZhbGxiYWNrLCBidXQgbmV2ZXIgZ3Vlc3MgYW1vbmcgZHVwbGljYXRlcy4KICAgIGJhc2VuYW1lID0gUHVyZVBvc2l4UGF0aChub3JtYWxpemVkKS5uYW1lLmNhc2Vmb2xkKCkKICAgIG1hdGNoZXMgPSBbXQogICAgZm9yIHAgaW4gcm9vdC5yZ2xvYigiKi5tZCIpOgogICAgICAgIHRyeToKICAgICAgICAgICAgaWYgcC5pc19maWxlKCkgYW5kIG5vdCBwLmlzX3N5bWxpbmsoKSBhbmQgcC5uYW1lLmNhc2Vmb2xkKCkgPT0gYmFzZW5hbWU6CiAgICAgICAgICAgICAgICBtYXRjaGVzLmFwcGVuZChwKQogICAgICAgIGV4Y2VwdCBPU0Vycm9yOgogICAgICAgICAgICBjb250aW51ZQogICAgbWF0Y2hlcyA9IHNvcnRlZChtYXRjaGVzLCBrZXk9bGFtYmRhIHA6IHAucmVsYXRpdmVfdG8ocm9vdCkuYXNfcG9zaXgoKS5jYXNlZm9sZCgpKQogICAgaWYgbGVuKG1hdGNoZXMpID09IDE6CiAgICAgICAgY2FuZGlkYXRlID0gbWF0Y2hlc1swXQogICAgICAgIG1hdGNoX21vZGUgPSAidW5pcXVlLWJhc2VuYW1lIgogICAgZWxpZiBsZW4obWF0Y2hlcykgPiAxOgogICAgICAgIGVtaXQoewogICAgICAgICAgICAic3RhdHVzIjoiYW1iaWd1b3VzIiwKICAgICAgICAgICAgImVycm9yIjoibXVsdGlwbGVfYmFzZW5hbWVfbWF0Y2hlcyIsCiAgICAgICAgICAgICJyZXF1ZXN0ZWRfc291cmNlIjpyZXF1ZXN0ZWQsCiAgICAgICAgICAgICJtYXRjaF9jb3VudCI6bGVuKG1hdGNoZXMpLAogICAgICAgICAgICAibWF0Y2hlcyI6W3AucmVsYXRpdmVfdG8ocm9vdCkuYXNfcG9zaXgoKSBmb3IgcCBpbiBtYXRjaGVzWzoyMF1dLAogICAgICAgIH0sIDE1KQogICAgZWxzZToKICAgICAgICBlbWl0KHsKICAgICAgICAgICAgInN0YXR1cyI6Im5vdF9mb3VuZCIsCiAgICAgICAgICAgICJlcnJvciI6InNvdXJjZV9maWxlX25vdF9mb3VuZCIsCiAgICAgICAgICAgICJyZXF1ZXN0ZWRfc291cmNlIjpyZXF1ZXN0ZWQsCiAgICAgICAgfSwgMTYpCgp0cnk6CiAgICByZWFsID0gY2FuZGlkYXRlLnJlc29sdmUoc3RyaWN0PVRydWUpCiAgICByZWwgPSByZWFsLnJlbGF0aXZlX3RvKHJvb3RfcmVhbCkKZXhjZXB0IEV4Y2VwdGlvbjoKICAgIGVtaXQoewogICAgICAgICJzdGF0dXMiOiJlcnJvciIsCiAgICAgICAgImVycm9yIjoicmVzb2x2ZWRfcGF0aF9vdXRzaWRlX3ZhdWx0IiwKICAgICAgICAicmVxdWVzdGVkX3NvdXJjZSI6cmVxdWVzdGVkLAogICAgfSwgMTcpCgppZiByZWFsLnN1ZmZpeC5jYXNlZm9sZCgpICE9ICIubWQiOgogICAgZW1pdCh7CiAgICAgICAgInN0YXR1cyI6ImVycm9yIiwKICAgICAgICAiZXJyb3IiOiJub25fbWFya2Rvd25fc291cmNlX3JlamVjdGVkIiwKICAgICAgICAicmVsYXRpdmVfcGF0aCI6cmVsLmFzX3Bvc2l4KCksCiAgICB9LCAxOCkKCmRhdGEgPSByZWFsLnJlYWRfYnl0ZXMoKQpkaWdlc3QgPSBoYXNobGliLnNoYTI1NihkYXRhKS5oZXhkaWdlc3QoKQoKcmVzdWx0ID0gewogICAgInN0YXR1cyI6Im9rIiwKICAgICJyZXF1ZXN0ZWRfc291cmNlIjpyZXF1ZXN0ZWQsCiAgICAibWF0Y2hfbW9kZSI6bWF0Y2hfbW9kZSwKICAgICJyZWxhdGl2ZV9wYXRoIjpyZWwuYXNfcG9zaXgoKSwKICAgICJzaXplX2J5dGVzIjpsZW4oZGF0YSksCiAgICAic2hhMjU2IjpkaWdlc3QsCn0KCmlmIHJlYWRfY29udGVudDoKICAgIHRyeToKICAgICAgICB0ZXh0ID0gZGF0YS5kZWNvZGUoInV0Zi04IikKICAgIGV4Y2VwdCBVbmljb2RlRGVjb2RlRXJyb3I6CiAgICAgICAgZW1pdCh7CiAgICAgICAgICAgICoqcmVzdWx0LAogICAgICAgICAgICAic3RhdHVzIjoiZXJyb3IiLAogICAgICAgICAgICAiZXJyb3IiOiJzb3VyY2Vfbm90X3V0ZjgiLAogICAgICAgIH0sIDE5KQogICAgcmVzdWx0WyJjb250ZW50Il0gPSB0ZXh0WzptYXhfY2hhcnNdCiAgICByZXN1bHRbImNoYXJzX3JldHVybmVkIl0gPSBtaW4obGVuKHRleHQpLCBtYXhfY2hhcnMpCiAgICByZXN1bHRbInRydW5jYXRlZCJdID0gbGVuKHRleHQpID4gbWF4X2NoYXJzCgplbWl0KHJlc3VsdCwgMCkK"

function Invoke-DockerJson {
    param(
        [Parameter(Mandatory = $true)][string[]]$Args
    )

    $raw = & docker @Args 2>&1
    $code = $LASTEXITCODE
    $text = (($raw | ForEach-Object { [string]$_ }) -join "`n").Trim()

    if ([string]::IsNullOrWhiteSpace($text)) {
        throw "Docker command returned no JSON output."
    }

    try {
        $obj = $text | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw ("Docker command returned non-JSON output (exit {0}): {1}" -f $code, $text)
    }

    return [pscustomobject]@{
        ExitCode = $code
        Object = $obj
    }
}

$running = @(& docker ps --format "{{.Names}}")
if ($LASTEXITCODE -ne 0) {
    throw "Could not list running Docker containers."
}
if ($running -notcontains $VaultContainer) {
    throw "Exact vault sidecar '$VaultContainer' is not running."
}

$resolvedSource = $SourcePath
$resolvedRecord = $null

if ($PSCmdlet.ParameterSetName -eq "ByRecord") {
    if ($running -notcontains $MemoryContainer) {
        throw "iai vault-watch container '$MemoryContainer' is not running."
    }

    $lookupLoader = "import base64; exec(base64.b64decode('$LookupPayload'))"
    $lookup = Invoke-DockerJson -Args @(
        "exec",
        "-u", "10000:10000",
        "-e", "HOME=/opt/data/profiles/companion",
        "-e", "IAI_MCP_STORE=/opt/data/profiles/companion/.iai-mcp",
        "-e", "IAI_DAEMON_SOCKET_PATH=/opt/data/profiles/companion/.iai-mcp/.daemon.sock",
        "-e", ("ORION_RECORD_ID={0}" -f $RecordId),
        $MemoryContainer,
        "/opt/iai/venv/bin/python", "-c", $lookupLoader
    )

    if ($lookup.ExitCode -ne 0 -or $lookup.Object.status -ne "ok") {
        throw ("Could not resolve iai record provenance: {0}" -f ($lookup.Object | ConvertTo-Json -Compress -Depth 5))
    }

    $resolvedRecord = [string]$lookup.Object.record_id
    $resolvedSource = [string]$lookup.Object.source_path
}

if ([string]::IsNullOrWhiteSpace($resolvedSource)) {
    throw "No source path was available to resolve."
}

$resolverLoader = "import base64; exec(base64.b64decode('$ResolverPayload'))"
$readFlag = if ($Read) { "1" } else { "0" }

$resolve = Invoke-DockerJson -Args @(
    "exec",
    "-u", "10000:10000",
    "-e", ("ORION_SOURCE_PATH={0}" -f $resolvedSource),
    "-e", ("ORION_READ_CONTENT={0}" -f $readFlag),
    "-e", ("ORION_MAX_CHARS={0}" -f $MaxChars),
    $VaultContainer,
    "/opt/iai/venv/bin/python", "-c", $resolverLoader
)

if ($resolve.ExitCode -ne 0 -or $resolve.Object.status -ne "ok") {
    throw ("Exact vault resolution failed: {0}" -f ($resolve.Object | ConvertTo-Json -Compress -Depth 5))
}

$relativePath = [string]$resolve.Object.relative_path
$hostPath = Join-Path -Path $HostVaultRoot -ChildPath ($relativePath -replace "/", "\")

$result = [ordered]@{
    status = "ok"
    record_id = $resolvedRecord
    source_path = $resolvedSource
    match_mode = [string]$resolve.Object.match_mode
    relative_path = $relativePath
    host_path = $hostPath
    size_bytes = [int64]$resolve.Object.size_bytes
    sha256 = [string]$resolve.Object.sha256
}

if ($Read) {
    $result["content"] = [string]$resolve.Object.content
    $result["chars_returned"] = [int]$resolve.Object.chars_returned
    $result["truncated"] = [bool]$resolve.Object.truncated
}

if ($Json) {
    [pscustomobject]$result | ConvertTo-Json -Depth 5
}
else {
    Write-Host "ORION_EXACT_VAULT_RESOLVER=PASS"
    if ($resolvedRecord) {
        Write-Host "RECORD_ID=$resolvedRecord"
    }
    Write-Host "SOURCE_PATH=$resolvedSource"
    Write-Host ("MATCH_MODE={0}" -f $result.match_mode)
    Write-Host ("HOST_PATH={0}" -f $result.host_path)
    Write-Host ("SIZE_BYTES={0}" -f $result.size_bytes)
    Write-Host ("SHA256={0}" -f $result.sha256)
    if ($Read) {
        Write-Host ("CHARS_RETURNED={0}" -f $result.chars_returned)
        Write-Host ("TRUNCATED={0}" -f $result.truncated)
        Write-Host ""
        Write-Output $result.content
    }
}
