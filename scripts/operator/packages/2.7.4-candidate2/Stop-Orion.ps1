[CmdletBinding()]
param([string]$ConfigPath)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    if ([string]::IsNullOrWhiteSpace($PSScriptRoot)) {
        throw "Unable to resolve Orion operator publication directory."
    }
    $ConfigPath = Join-Path $PSScriptRoot "orion-config.json"
}

$invokePath = Join-Path $PSScriptRoot "Invoke-Orion.ps1"
& $invokePath -Action stop -ConfigPath $ConfigPath
exit $LASTEXITCODE
