[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Title,

    [Parameter(Mandatory = $true)]
    [string]$Body,

    [string]$Filename,

    [switch]$Json
)

$ErrorActionPreference = "Stop"

$Container = "orion-inbox-writer"
$Payload = "CmltcG9ydCBiYXNlNjQsIGpzb24sIG9zLCByZQpmcm9tIHBhdGhsaWIgaW1wb3J0IFBhdGgsIFB1cmVQb3NpeFBhdGgKZnJvbSBkYXRldGltZSBpbXBvcnQgZGF0ZXRpbWUsIHRpbWV6b25lCgpyb290ID0gUGF0aCgiL2luYm94IikKZmlsZW5hbWUgPSAob3MuZW52aXJvbi5nZXQoIk9SSU9OX0RSQUZUX0ZJTEVOQU1FIikgb3IgIiIpLnN0cmlwKCkKdGl0bGUgPSAob3MuZW52aXJvbi5nZXQoIk9SSU9OX0RSQUZUX1RJVExFIikgb3IgIiIpLnN0cmlwKCkKYm9keV9iNjQgPSBvcy5lbnZpcm9uLmdldCgiT1JJT05fRFJBRlRfQk9EWV9CNjQiKSBvciAiIgoKZGVmIGVtaXQob2JqLCBjb2RlPTApOgogICAgcHJpbnQoanNvbi5kdW1wcyhvYmosIGVuc3VyZV9hc2NpaT1GYWxzZSkpCiAgICByYWlzZSBTeXN0ZW1FeGl0KGNvZGUpCgppZiBub3Qgcm9vdC5pc19kaXIoKToKICAgIGVtaXQoeyJzdGF0dXMiOiJlcnJvciIsImVycm9yIjoiaW5ib3hfcm9vdF9taXNzaW5nIn0sIDEwKQoKaWYgbm90IGZpbGVuYW1lOgogICAgZW1pdCh7InN0YXR1cyI6ImVycm9yIiwiZXJyb3IiOiJmaWxlbmFtZV9yZXF1aXJlZCJ9LCAxMSkKCm5vcm1hbGl6ZWQgPSBmaWxlbmFtZS5yZXBsYWNlKCJcXCIsICIvIikKcCA9IFB1cmVQb3NpeFBhdGgobm9ybWFsaXplZCkKCmlmIHAuaXNfYWJzb2x1dGUoKSBvciBsZW4ocC5wYXJ0cykgIT0gMToKICAgIGVtaXQoeyJzdGF0dXMiOiJlcnJvciIsImVycm9yIjoibmVzdGVkX29yX2Fic29sdXRlX3BhdGhfcmVqZWN0ZWQiLCJmaWxlbmFtZSI6ZmlsZW5hbWV9LCAxMikKCm5hbWUgPSBwLm5hbWUKaWYgbmFtZSBpbiAoIiIsICIuIiwgIi4uIikgb3IgIi8iIGluIG5hbWUgb3IgIlxcIiBpbiBuYW1lOgogICAgZW1pdCh7InN0YXR1cyI6ImVycm9yIiwiZXJyb3IiOiJpbnZhbGlkX2ZpbGVuYW1lIiwiZmlsZW5hbWUiOmZpbGVuYW1lfSwgMTMpCgppZiBub3QgbmFtZS5sb3dlcigpLmVuZHN3aXRoKCIubWQiKToKICAgIGVtaXQoeyJzdGF0dXMiOiJlcnJvciIsImVycm9yIjoibWFya2Rvd25fZXh0ZW5zaW9uX3JlcXVpcmVkIiwiZmlsZW5hbWUiOmZpbGVuYW1lfSwgMTQpCgojIFJlc3RyaWN0IHRvIGEgY29uc2VydmF0aXZlIGZpbGVuYW1lIGNoYXJhY3RlciBzZXQuCmlmIG5vdCByZS5mdWxsbWF0Y2gociJbQS1aYS16MC05XVtBLVphLXowLTkuXyAtXXswLDExOX1cLm1kIiwgbmFtZSk6CiAgICBlbWl0KHsic3RhdHVzIjoiZXJyb3IiLCJlcnJvciI6InVuc2FmZV9maWxlbmFtZSIsImZpbGVuYW1lIjpmaWxlbmFtZX0sIDE1KQoKdGFyZ2V0ID0gcm9vdCAvIG5hbWUKaWYgdGFyZ2V0LmV4aXN0cygpOgogICAgZW1pdCh7InN0YXR1cyI6ImVycm9yIiwiZXJyb3IiOiJkcmFmdF9hbHJlYWR5X2V4aXN0cyIsImZpbGVuYW1lIjpuYW1lfSwgMTYpCgp0cnk6CiAgICBib2R5ID0gYmFzZTY0LmI2NGRlY29kZShib2R5X2I2NC5lbmNvZGUoImFzY2lpIiksIHZhbGlkYXRlPVRydWUpLmRlY29kZSgidXRmLTgiKQpleGNlcHQgRXhjZXB0aW9uOgogICAgZW1pdCh7InN0YXR1cyI6ImVycm9yIiwiZXJyb3IiOiJpbnZhbGlkX2JvZHlfZW5jb2RpbmcifSwgMTcpCgppZiBsZW4oYm9keSkgPiAxMDBfMDAwOgogICAgZW1pdCh7InN0YXR1cyI6ImVycm9yIiwiZXJyb3IiOiJkcmFmdF90b29fbGFyZ2UiLCJtYXhfY2hhcnMiOjEwMDAwMH0sIDE4KQoKY3JlYXRlZCA9IGRhdGV0aW1lLm5vdyh0aW1lem9uZS51dGMpLnJlcGxhY2UobWljcm9zZWNvbmQ9MCkuaXNvZm9ybWF0KCkKc2FmZV90aXRsZSA9IHRpdGxlIG9yIHRhcmdldC5zdGVtCgpjb250ZW50ID0gKAogICAgIi0tLVxuIgogICAgIm9yaW9uX2RyYWZ0OiB0cnVlXG4iCiAgICAic3RhdHVzOiBkcmFmdFxuIgogICAgImdlbmVyYXRlZF9ieTogT3Jpb25cbiIKICAgIGYiY3JlYXRlZF9hdDoge2NyZWF0ZWR9XG4iCiAgICAiLS0tXG5cbiIKICAgIGYiIyB7c2FmZV90aXRsZX1cblxuIgogICAgZiJ7Ym9keS5yc3RyaXAoKX1cbiIKKQoKIyBFeGNsdXNpdmUgY3JlYXRlOiBuZXZlciBvdmVyd3JpdGUgYW4gZXhpc3RpbmcgZHJhZnQuCndpdGggdGFyZ2V0Lm9wZW4oIngiLCBlbmNvZGluZz0idXRmLTgiLCBuZXdsaW5lPSJcbiIpIGFzIGY6CiAgICBmLndyaXRlKGNvbnRlbnQpCgpkYXRhID0gdGFyZ2V0LnJlYWRfYnl0ZXMoKQplbWl0KHsKICAgICJzdGF0dXMiOiJvayIsCiAgICAiZmlsZW5hbWUiOm5hbWUsCiAgICAicGF0aCI6ZiIvaW5ib3gve25hbWV9IiwKICAgICJzaXplX2J5dGVzIjpsZW4oZGF0YSksCiAgICAiY3JlYXRlZF9hdCI6Y3JlYXRlZCwKICAgICJvcmlvbl9kcmFmdCI6VHJ1ZSwKfSwgMCkK"

function ConvertTo-SafeDraftFilename {
    param([Parameter(Mandatory = $true)][string]$InputTitle)

    $slug = $InputTitle.Trim()
    $slug = [regex]::Replace($slug, '[^A-Za-z0-9._ -]+', '-')
    $slug = [regex]::Replace($slug, '\s+', ' ')
    $slug = $slug.Trim(' ', '.', '-')
    if ([string]::IsNullOrWhiteSpace($slug)) {
        $slug = "Orion Draft"
    }
    if ($slug.Length -gt 80) {
        $slug = $slug.Substring(0, 80).Trim()
    }
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    return ("{0} - {1}.md" -f $stamp, $slug)
}

if ([string]::IsNullOrWhiteSpace($Filename)) {
    $Filename = ConvertTo-SafeDraftFilename -InputTitle $Title
}

$running = @(& docker ps --format "{{.Names}}")
if ($LASTEXITCODE -ne 0) {
    throw "Could not list running Docker containers."
}
if ($running -notcontains $Container) {
    throw "Dedicated Orion inbox container '$Container' is not running."
}

$bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($Body)
$bodyB64 = [Convert]::ToBase64String($bodyBytes)
$loader = "import base64; exec(base64.b64decode('$Payload'))"

$raw = & docker exec `
    -u 10000:10000 `
    -e ("ORION_DRAFT_FILENAME={0}" -f $Filename) `
    -e ("ORION_DRAFT_TITLE={0}" -f $Title) `
    -e ("ORION_DRAFT_BODY_B64={0}" -f $bodyB64) `
    $Container `
    /opt/iai/venv/bin/python -c $loader 2>&1

$code = $LASTEXITCODE
$text = (($raw | ForEach-Object { [string]$_ }) -join "`n").Trim()

if ([string]::IsNullOrWhiteSpace($text)) {
    throw "Draft creator returned no output."
}

try {
    $obj = $text | ConvertFrom-Json -ErrorAction Stop
}
catch {
    throw ("Draft creator returned non-JSON output (exit {0}): {1}" -f $code, $text)
}

if ($code -ne 0 -or $obj.status -ne "ok") {
    throw ("Draft creation failed: {0}" -f ($obj | ConvertTo-Json -Compress -Depth 5))
}

if ($Json) {
    $obj | ConvertTo-Json -Depth 5
}
else {
    Write-Host "ORION_INBOX_DRAFT_CREATE=PASS"
    Write-Host ("FILENAME={0}" -f $obj.filename)
    Write-Host ("INBOX_PATH={0}" -f $obj.path)
    Write-Host ("SIZE_BYTES={0}" -f $obj.size_bytes)
    Write-Host ("CREATED_AT={0}" -f $obj.created_at)
}
