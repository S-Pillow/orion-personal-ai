[CmdletBinding()]
param(
    [string]$WorkspaceRoot = "$HOME\Orion-Recovery",
    [switch]$ExecuteSourceSetup,
    [switch]$BuildRuntime
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Repos = @(
    [pscustomobject]@{
        Name = "orion-personal-ai"
        Url = "https://github.com/S-Pillow/orion-personal-ai.git"
        Branch = "main"
        Upstream = ""
    }
    [pscustomobject]@{
        Name = "jarvis_ai"
        Url = "https://github.com/S-Pillow/jarvis_ai.git"
        Branch = "orion-mvp"
        Upstream = "https://github.com/eadmin2/jarvis_ai.git"
    }
    [pscustomobject]@{
        Name = "iai-personal-memory-engine"
        Url = "https://github.com/S-Pillow/iai-personal-memory-engine.git"
        Branch = "main"
        Upstream = "https://github.com/CodeAbra/iai-personal-memory-engine.git"
    }
)

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$AllowFailure
    )

    $saved = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $raw = & git @Arguments 2>&1
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $saved
    }

    $text = (($raw | ForEach-Object { [string]$_ }) -join [Environment]::NewLine).Trim()

    if (($code -ne 0) -and (-not $AllowFailure)) {
        throw ("Git failed with exit {0}: git {1}{2}{3}" -f $code, ($Arguments -join " "), [Environment]::NewLine, $text)
    }

    return [pscustomobject]@{
        ExitCode = $code
        Text = $text
    }
}

function Assert-Origin {
    param(
        [Parameter(Mandatory = $true)][string]$RepoPath,
        [Parameter(Mandatory = $true)][string]$ExpectedUrl
    )

    $origin = (Invoke-Git -Arguments @("-C", $RepoPath, "remote", "get-url", "origin")).Text
    if ($origin -notin @($ExpectedUrl, $ExpectedUrl.TrimEnd(".git"))) {
        throw ("Unexpected origin for {0}: {1}" -f $RepoPath, $origin)
    }
}

Write-Host "Orion recovery workspace bootstrap"
Write-Host ("WorkspaceRoot={0}" -f $WorkspaceRoot)
Write-Host ""

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is required but was not found in PATH."
}

if ($BuildRuntime -and (-not $ExecuteSourceSetup)) {
    throw "-BuildRuntime requires -ExecuteSourceSetup."
}

if (-not $ExecuteSourceSetup) {
    Write-Host "ORION_RECOVERY_MODE=PLAN_ONLY"
    foreach ($repo in $Repos) {
        Write-Host ("PLAN_REPO={0}|branch={1}|url={2}" -f $repo.Name, $repo.Branch, $repo.Url)
    }
    Write-Host "PLAN_PRIVATE_MATERIAL=credentials,iai-backup-or-key,obsidian-vault"
    Write-Host "PLAN_BUILD_RUNTIME=optional-via-BuildRuntime"
    Write-Host "ORION_RECOVERY_PLAN=PASS"
    exit 0
}

if (-not (Test-Path -LiteralPath $WorkspaceRoot -PathType Container)) {
    New-Item -ItemType Directory -Path $WorkspaceRoot -Force | Out-Null
}

foreach ($repo in $Repos) {
    $repoPath = Join-Path -Path $WorkspaceRoot -ChildPath $repo.Name

    if (-not (Test-Path -LiteralPath $repoPath -PathType Container)) {
        Invoke-Git -Arguments @("clone", $repo.Url, $repoPath) | Out-Null
    }
    elseif (-not (Test-Path -LiteralPath (Join-Path $repoPath ".git") -PathType Container)) {
        throw ("Existing path is not a Git repository: {0}" -f $repoPath)
    }

    Assert-Origin -RepoPath $repoPath -ExpectedUrl $repo.Url

    $status = (Invoke-Git -Arguments @("-C", $repoPath, "status", "--porcelain")).Text
    if (-not [string]::IsNullOrWhiteSpace($status)) {
        throw ("Repository has local changes and will not be changed automatically: {0}{1}{2}" -f $repoPath, [Environment]::NewLine, $status)
    }

    Invoke-Git -Arguments @("-C", $repoPath, "fetch", "origin") | Out-Null

    $branchExists = Invoke-Git -AllowFailure -Arguments @(
        "-C", $repoPath,
        "show-ref", "--verify", "--quiet",
        ("refs/heads/{0}" -f $repo.Branch)
    )

    if ($branchExists.ExitCode -eq 0) {
        Invoke-Git -Arguments @("-C", $repoPath, "checkout", $repo.Branch) | Out-Null
    }
    else {
        Invoke-Git -Arguments @(
            "-C", $repoPath,
            "checkout", "-b", $repo.Branch,
            ("origin/{0}" -f $repo.Branch)
        ) | Out-Null
    }

    Invoke-Git -Arguments @("-C", $repoPath, "pull", "--ff-only", "origin", $repo.Branch) | Out-Null

    if (-not [string]::IsNullOrWhiteSpace($repo.Upstream)) {
        $upstream = Invoke-Git -AllowFailure -Arguments @("-C", $repoPath, "remote", "get-url", "upstream")

        if ($upstream.ExitCode -ne 0) {
            Invoke-Git -Arguments @("-C", $repoPath, "remote", "add", "upstream", $repo.Upstream) | Out-Null
        }
        elseif ($upstream.Text -notin @($repo.Upstream, $repo.Upstream.TrimEnd(".git"))) {
            throw ("Unexpected upstream for {0}: {1}" -f $repo.Name, $upstream.Text)
        }
    }

    Write-Host ("ORION_RECOVERY_REPO_READY={0}|branch={1}" -f $repo.Name, $repo.Branch)
}

$orionRepo = Join-Path -Path $WorkspaceRoot -ChildPath "orion-personal-ai"
$rebuildScript = Join-Path -Path $orionRepo -ChildPath "build\orion-runtime\rebuild\build-orion-runtime.ps1"

if (-not (Test-Path -LiteralPath $rebuildScript -PathType Leaf)) {
    throw "Canonical Orion runtime rebuild script was not found."
}

$parseErrors = $null
$tokens = $null
[System.Management.Automation.Language.Parser]::ParseFile(
    $rebuildScript,
    [ref]$tokens,
    [ref]$parseErrors
) | Out-Null

if ($parseErrors.Count -ne 0) {
    throw ("Canonical rebuild script has parser errors: {0}" -f (($parseErrors | ForEach-Object { $_.ToString() }) -join "; "))
}

Write-Host "ORION_RECOVERY_REBUILD_SOURCE=PASS"

if ($BuildRuntime) {
    if (-not (Get-Command docker.exe -ErrorAction SilentlyContinue)) {
        throw "docker.exe is required for -BuildRuntime."
    }

    $tagPrefix = "orion-recovery-" + [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss").ToLowerInvariant()
    $buildArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $rebuildScript,
        "-Execute",
        "-TagPrefix", $tagPrefix
    )

    & powershell.exe @buildArgs

    if ($LASTEXITCODE -ne 0) {
        throw ("Canonical runtime rebuild failed with exit {0}." -f $LASTEXITCODE)
    }

    Write-Host ("ORION_RECOVERY_BUILD_TAG_PREFIX={0}" -f $tagPrefix)
    Write-Host "ORION_RECOVERY_RUNTIME_BUILD=PASS"
}
else {
    Write-Host "ORION_RECOVERY_RUNTIME_BUILD=SKIPPED"
}

Write-Host "ORION_RECOVERY_PRIVATE_DATA_RESTORE=MANUAL"
Write-Host "ORION_RECOVERY_SOURCE_SETUP=PASS"
