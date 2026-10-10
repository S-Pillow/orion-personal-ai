[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('start','stop','recover','preflight')][string]$Action,
    [string]$ConfigPath
)
Set-StrictMode -Version 3.0
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    if ([string]::IsNullOrWhiteSpace($PSScriptRoot)) {
        throw 'Unable to resolve Orion operator publication directory.'
    }
    $ConfigPath = Join-Path $PSScriptRoot 'orion-config.json'
}
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    throw 'Create orion-config.json from the example after checking Discover-Orion.ps1 output.'
}
$resolvedConfig = (Resolve-Path -LiteralPath $ConfigPath).Path
$settings = Get-Content -LiteralPath $resolvedConfig -Raw | ConvertFrom-Json
if ($settings.python -isnot [string] -or
    -not (Test-Path -LiteralPath $settings.python -PathType Leaf)) {
    throw 'The configured Hermes Python executable does not exist.'
}
# This is a one-shot application invocation. Python owns the canonical lock,
# records, process handles, worker deadlines, and all lifecycle decisions.
& $settings.python -E -s (Join-Path $PSScriptRoot 'orion.py') $Action --config $resolvedConfig
exit $LASTEXITCODE
