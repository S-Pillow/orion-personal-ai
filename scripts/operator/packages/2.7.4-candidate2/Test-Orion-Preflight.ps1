[CmdletBinding()]
param([string]$ConfigPath = (Join-Path $PSScriptRoot 'orion-config.json'))
& (Join-Path $PSScriptRoot 'Invoke-Orion.ps1') -Action preflight -ConfigPath $ConfigPath
exit $LASTEXITCODE
