[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$DraftFile,

    [ValidateRange(1, 10)]
    [int]$Top = 5,

    [switch]$Json
)

$ErrorActionPreference = "Stop"

$InboxRoot = "C:\Personal\Orion-Inbox"
$VaultRoot = "C:\Personal\Me"
$MemoryContainer = "orion-iai-vault-watch"
$Payload = "CmltcG9ydCBiYXNlNjQKaW1wb3J0IGpzb24KaW1wb3J0IG9zCmZyb20gcGF0aGxpYiBpbXBvcnQgUHVyZVBvc2l4UGF0aApmcm9tIHV1aWQgaW1wb3J0IFVVSUQKCmZyb20gaWFpX21jcC5pYWlfY2xpIGltcG9ydCBfb3Blbl9zdG9yZV9zaGFyZWQsIF9yZWxheV9ycGMKCmN1ZV9iNjQgPSBvcy5lbnZpcm9uLmdldCgiT1JJT05fUDNfMDZfQ1VFX0I2NCIpIG9yICIiCnRyeToKICAgIGN1ZSA9IGJhc2U2NC5iNjRkZWNvZGUoY3VlX2I2NC5lbmNvZGUoImFzY2lpIiksIHZhbGlkYXRlPVRydWUpLmRlY29kZSgidXRmLTgiKQpleGNlcHQgRXhjZXB0aW9uOgogICAgcHJpbnQoanNvbi5kdW1wcyh7InN0YXR1cyI6ImVycm9yIiwiZXJyb3IiOiJpbnZhbGlkX2N1ZV9lbmNvZGluZyJ9KSkKICAgIHJhaXNlIFN5c3RlbUV4aXQoMTApCgpjdWUgPSBjdWUuc3RyaXAoKQppZiBub3QgY3VlOgogICAgcHJpbnQoanNvbi5kdW1wcyh7InN0YXR1cyI6ImVycm9yIiwiZXJyb3IiOiJlbXB0eV9jdWUifSkpCiAgICByYWlzZSBTeXN0ZW1FeGl0KDExKQoKcmVzcCA9IF9yZWxheV9ycGMoCiAgICAibWVtb3J5X3JlY2FsbCIsCiAgICB7ImN1ZSI6IGN1ZVs6NDAwMF0sICJidWRnZXRfdG9rZW5zIjogMjAwMH0sCiAgICB0aW1lb3V0PTMwLjAsCikKaWYgbm90IGlzaW5zdGFuY2UocmVzcCwgZGljdCkgb3IgcmVzcC5nZXQoInN0YXR1cyIpIGluICgiZGFlbW9uX2Rvd24iLCAiZXJyb3IiKToKICAgIHByaW50KGpzb24uZHVtcHMoeyJzdGF0dXMiOiJlcnJvciIsImVycm9yIjoibWVtb3J5X3JlY2FsbF9mYWlsZWQifSkpCiAgICByYWlzZSBTeXN0ZW1FeGl0KDEyKQoKaGl0cyA9IFtoIGZvciBoIGluIChyZXNwLmdldCgiaGl0cyIpIG9yIFtdKSBpZiBpc2luc3RhbmNlKGgsIGRpY3QpXQoKc3RvcmUgPSBfb3Blbl9zdG9yZV9zaGFyZWQoKQp0cnk6CiAgICBjYW5kaWRhdGVzID0gW10KICAgIHNlZW5fZGlycyA9IHNldCgpCgogICAgZm9yIHJhbmssIGhpdCBpbiBlbnVtZXJhdGUoaGl0cywgc3RhcnQ9MSk6CiAgICAgICAgcmlkX3JhdyA9IHN0cihoaXQuZ2V0KCJyZWNvcmRfaWQiKSBvciBoaXQuZ2V0KCJpZCIpIG9yICIiKS5zdHJpcCgpCiAgICAgICAgaWYgbm90IHJpZF9yYXc6CiAgICAgICAgICAgIGNvbnRpbnVlCiAgICAgICAgdHJ5OgogICAgICAgICAgICByZWMgPSBzdG9yZS5nZXQoVVVJRChyaWRfcmF3KSkKICAgICAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgICAgICByZWMgPSBOb25lCiAgICAgICAgaWYgcmVjIGlzIE5vbmU6CiAgICAgICAgICAgIGNvbnRpbnVlCgogICAgICAgIHByb3ZzID0gW3AgZm9yIHAgaW4gKHJlYy5wcm92ZW5hbmNlIG9yIFtdKSBpZiBpc2luc3RhbmNlKHAsIGRpY3QpXQogICAgICAgIGlmIG5vdCBhbnkocC5nZXQoInNlc3Npb25faWQiKSA9PSAidmF1bHQtc3R1ZHkiIGZvciBwIGluIHByb3ZzKToKICAgICAgICAgICAgY29udGludWUKCiAgICAgICAgc3R1ZHkgPSBbCiAgICAgICAgICAgIHAgZm9yIHAgaW4gcHJvdnMKICAgICAgICAgICAgaWYgcC5nZXQoInNvdXJjZSIpID09ICJzdHVkeSIgYW5kIHAuZ2V0KCJmaWxlbmFtZSIpCiAgICAgICAgXQogICAgICAgIGlmIG5vdCBzdHVkeToKICAgICAgICAgICAgY29udGludWUKCiAgICAgICAgc291cmNlID0gc3RyKHN0dWR5WzBdWyJmaWxlbmFtZSJdKS5yZXBsYWNlKCJcXCIsICIvIikuc3RyaXAoIi8iKQogICAgICAgIGlmIG5vdCBzb3VyY2UubG93ZXIoKS5lbmRzd2l0aCgiLm1kIik6CiAgICAgICAgICAgIGNvbnRpbnVlCgogICAgICAgIHBhdGggPSBQdXJlUG9zaXhQYXRoKHNvdXJjZSkKICAgICAgICBwYXJlbnQgPSBwYXRoLnBhcmVudC5hc19wb3NpeCgpCiAgICAgICAgaWYgcGFyZW50ID09ICIuIjoKICAgICAgICAgICAgcGFyZW50ID0gIiIKCiAgICAgICAga2V5ID0gcGFyZW50LmNhc2Vmb2xkKCkKICAgICAgICBpZiBrZXkgaW4gc2Vlbl9kaXJzOgogICAgICAgICAgICBjb250aW51ZQogICAgICAgIHNlZW5fZGlycy5hZGQoa2V5KQoKICAgICAgICBjYW5kaWRhdGVzLmFwcGVuZCh7CiAgICAgICAgICAgICJuYXRpdmVfcmVjYWxsX3JhbmsiOiByYW5rLAogICAgICAgICAgICAiZGlyZWN0b3J5IjogcGFyZW50LAogICAgICAgICAgICAic291cmNlX3BhdGgiOiBzb3VyY2UsCiAgICAgICAgICAgICJyZWNvcmRfaWQiOiByaWRfcmF3LAogICAgICAgIH0pCmZpbmFsbHk6CiAgICB0cnk6CiAgICAgICAgc3RvcmUuY2xvc2UoKQogICAgZXhjZXB0IEV4Y2VwdGlvbjoKICAgICAgICBwYXNzCgpwcmludChqc29uLmR1bXBzKHsKICAgICJzdGF0dXMiOiJvayIsCiAgICAiaGl0X2NvdW50IjpsZW4oaGl0cyksCiAgICAiY2FuZGlkYXRlcyI6Y2FuZGlkYXRlcywKfSwgZW5zdXJlX2FzY2lpPUZhbHNlKSkKcmFpc2UgU3lzdGVtRXhpdCgwKQo="

function Get-FullPathUnderRoot {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Relative
    )

    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
    $candidate = Join-Path -Path $rootFull -ChildPath ($Relative -replace "/", "\")
    $full = [System.IO.Path]::GetFullPath($candidate)

    if (-not $full.StartsWith($rootFull + "\", [System.StringComparison]::OrdinalIgnoreCase) -and
        -not $full.Equals($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Resolved path escapes the expected root."
    }

    return $full
}

# Drafts are intentionally flat in the dedicated inbox.
if ([System.IO.Path]::IsPathRooted($DraftFile) -or
    $DraftFile.Contains("/") -or
    $DraftFile.Contains("\") -or
    -not $DraftFile.EndsWith(".md", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "DraftFile must be one Markdown filename from the Orion inbox."
}

$draftPath = Join-Path -Path $InboxRoot -ChildPath $DraftFile
if (-not (Test-Path -LiteralPath $draftPath -PathType Leaf)) {
    throw "Inbox draft not found: $draftPath"
}

$draftText = [System.IO.File]::ReadAllText($draftPath)
if ([string]::IsNullOrWhiteSpace($draftText)) {
    throw "Inbox draft is empty."
}
if ($draftText.Length -gt 100000) {
    throw "Inbox draft exceeds the 100000-character MVP limit."
}

$running = @(& docker ps --format "{{.Names}}")
if ($LASTEXITCODE -ne 0) {
    throw "Could not list running Docker containers."
}
if ($running -notcontains $MemoryContainer) {
    throw "Native iai vault-watch container '$MemoryContainer' is not running."
}

$cueBytes = [System.Text.Encoding]::UTF8.GetBytes($draftText)
$cueB64 = [Convert]::ToBase64String($cueBytes)
$loader = "import base64; exec(base64.b64decode('$Payload'))"

$raw = & docker exec `
    -u 10000:10000 `
    -e "HOME=/opt/data/profiles/companion" `
    -e "IAI_MCP_STORE=/opt/data/profiles/companion/.iai-mcp" `
    -e "IAI_DAEMON_SOCKET_PATH=/opt/data/profiles/companion/.iai-mcp/.daemon.sock" `
    -e ("ORION_P3_06_CUE_B64={0}" -f $cueB64) `
    $MemoryContainer `
    /opt/iai/venv/bin/python -c $loader 2>&1

$code = $LASTEXITCODE
$text = (($raw | ForEach-Object { [string]$_ }) -join "`n").Trim()
if ($code -ne 0) {
    throw ("Native iai destination-recall step failed (exit {0}): {1}" -f $code, $text)
}

try {
    $obj = $text | ConvertFrom-Json -ErrorAction Stop
}
catch {
    throw ("Native iai destination-recall step returned non-JSON: {0}" -f $text)
}

if ($obj.status -ne "ok") {
    throw ("Native iai destination-recall step returned non-ok status: {0}" -f $text)
}

$recommendations = @()
foreach ($candidate in @($obj.candidates)) {
    if ($recommendations.Count -ge $Top) {
        break
    }

    $relativeDir = [string]$candidate.directory
    if ($relativeDir -eq ".") {
        $relativeDir = ""
    }

    try {
        $hostDir = Get-FullPathUnderRoot -Root $VaultRoot -Relative $relativeDir
    }
    catch {
        continue
    }

    if (-not (Test-Path -LiteralPath $hostDir -PathType Container)) {
        continue
    }

    $suggestedTarget = if ([string]::IsNullOrWhiteSpace($relativeDir)) {
        $DraftFile
    }
    else {
        ("{0}/{1}" -f $relativeDir.TrimEnd("/"), $DraftFile)
    }

    $recommendations += [pscustomobject]@{
        rank = $recommendations.Count + 1
        directory = $relativeDir
        suggested_target_relative_path = $suggestedTarget
        evidence_source_path = [string]$candidate.source_path
        native_recall_rank = [int]$candidate.native_recall_rank
    }
}

$result = [pscustomobject]@{
    status = "ok"
    draft_file = $DraftFile
    native_recall_hit_count = [int]$obj.hit_count
    recommendation_count = $recommendations.Count
    recommendations = $recommendations
}

if ($Json) {
    $result | ConvertTo-Json -Depth 8
    exit 0
}

Write-Host "ORION_VAULT_DESTINATION_RECOMMENDER=PASS"
Write-Host ("DRAFT_FILE={0}" -f $DraftFile)
Write-Host ("NATIVE_RECALL_HITS={0}" -f $result.native_recall_hit_count)
Write-Host ("RECOMMENDATION_COUNT={0}" -f $result.recommendation_count)

$index = 0
foreach ($item in $recommendations) {
    $index++
    $displayDir = if ([string]::IsNullOrWhiteSpace([string]$item.directory)) { "<vault-root>" } else { [string]$item.directory }
    Write-Host ("RECOMMENDATION_{0}_DIRECTORY={1}" -f $index, $displayDir)
    Write-Host ("RECOMMENDATION_{0}_TARGET={1}" -f $index, $item.suggested_target_relative_path)
    Write-Host ("RECOMMENDATION_{0}_EVIDENCE_SOURCE={1}" -f $index, $item.evidence_source_path)
    Write-Host ("RECOMMENDATION_{0}_IAI_RANK={1}" -f $index, $item.native_recall_rank)
}

if ($recommendations.Count -eq 0) {
    Write-Host "DESTINATION_RECOMMENDATION=NONE"
    Write-Host "No current vault-study source directory was supported by native iai recall."
}
