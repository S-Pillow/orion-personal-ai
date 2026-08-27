[CmdletBinding()]
param(
    [string]$WorkspaceRoot = "E:\Orion-Phase2",
    [string]$ForkUrl = "https://github.com/S-Pillow/jarvis_ai.git"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$UpstreamUrl = "https://github.com/eadmin2/jarvis_ai.git"
$UpstreamCommit = "88998de8369e9d36f6d434b5e01feb93fcf1c33f"
$Workspace = Join-Path -Path $WorkspaceRoot -ChildPath "Orion-HUD"
$OrionBranch = "orion-mvp"

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$AllowFailure
    )

    $savedPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $raw = & $FilePath @Arguments 2>&1
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedPreference
    }

    $text = (($raw | ForEach-Object { [string]$_ }) -join "`n").Trim()

    if (($code -ne 0) -and (-not $AllowFailure)) {
        throw ("Native command failed (exit {0}): {1} {2}`n{3}" -f $code, $FilePath, ($Arguments -join " "), $text)
    }

    return [pscustomobject]@{
        ExitCode = $code
        Text = $text
    }
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$AllowFailure
    )

    return Invoke-Native -FilePath "git" -Arguments $Arguments -AllowFailure:$AllowFailure
}

function Replace-LiteralOrVerify {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Old,
        [Parameter(Mandatory = $true)][string]$New,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if ($Text.Contains($New)) {
        return $Text
    }

    if (-not $Text.Contains($Old)) {
        throw ("Expected upstream text not found for '{0}'. The pinned source may not match the expected HUD structure." -f $Label)
    }

    return $Text.Replace($Old, $New)
}

function Join-Lines {
    param([Parameter(Mandatory = $true)][string[]]$Lines)
    return ($Lines -join [Environment]::NewLine) + [Environment]::NewLine
}

Write-Host "P4-01 Revised v2 — fork-first Orion HUD adoption"
Write-Host "Uses S-Pillow's fork as origin and eadmin2/jarvis_ai as upstream."
Write-Host ""

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is required but was not found in PATH."
}
Write-Host "P4_01R2_GIT_AVAILABLE=PASS"

if (-not (Test-Path -LiteralPath $WorkspaceRoot -PathType Container)) {
    New-Item -ItemType Directory -Path $WorkspaceRoot -Force | Out-Null
}

$forkCheck = Invoke-Git -AllowFailure -Arguments @("ls-remote", "--heads", $ForkUrl)
if ($forkCheck.ExitCode -ne 0) {
    throw ("Could not access the Orion fork at {0}. Fork eadmin2/jarvis_ai into the S-Pillow account first, then rerun." -f $ForkUrl)
}
Write-Host ("P4_01R2_FORK_URL={0}" -f $ForkUrl)
Write-Host "P4_01R2_FORK_ACCESSIBLE=PASS"

if (-not (Test-Path -LiteralPath $Workspace)) {
    Write-Host "Cloning Orion fork..."
    Invoke-Git -Arguments @("clone", $ForkUrl, $Workspace) | Out-Null
}
elseif (-not (Test-Path -LiteralPath (Join-Path -Path $Workspace -ChildPath ".git") -PathType Container)) {
    throw ("Workspace exists but is not a Git repository: {0}" -f $Workspace)
}

$origin = Invoke-Git -AllowFailure -Arguments @("-C", $Workspace, "remote", "get-url", "origin")
if ($origin.ExitCode -ne 0) {
    Invoke-Git -Arguments @("-C", $Workspace, "remote", "add", "origin", $ForkUrl) | Out-Null
}
elseif ($origin.Text -ne $ForkUrl) {
    throw ("Existing origin does not match the intended Orion fork. Found: {0}" -f $origin.Text)
}
Write-Host "P4_01R2_ORIGIN_IS_FORK=PASS"

$upstream = Invoke-Git -AllowFailure -Arguments @("-C", $Workspace, "remote", "get-url", "upstream")
if ($upstream.ExitCode -ne 0) {
    Invoke-Git -Arguments @("-C", $Workspace, "remote", "add", "upstream", $UpstreamUrl) | Out-Null
}
elseif ($upstream.Text -ne $UpstreamUrl) {
    throw ("Existing upstream remote is unexpected. Found: {0}" -f $upstream.Text)
}
Write-Host "P4_01R2_UPSTREAM_REMOTE=PASS"

$havePinned = Invoke-Git -AllowFailure -Arguments @("-C", $Workspace, "cat-file", "-e", ("{0}^{{commit}}" -f $UpstreamCommit))
if ($havePinned.ExitCode -ne 0) {
    Invoke-Git -Arguments @("-C", $Workspace, "fetch", "upstream", $UpstreamCommit) | Out-Null
}

$resolvedPinned = (Invoke-Git -Arguments @("-C", $Workspace, "rev-parse", $UpstreamCommit)).Text
if ($resolvedPinned -ne $UpstreamCommit) {
    throw ("Pinned upstream commit mismatch. Expected {0}; got {1}" -f $UpstreamCommit, $resolvedPinned)
}
Write-Host ("P4_01R2_UPSTREAM_COMMIT={0}" -f $UpstreamCommit)
Write-Host "P4_01R2_UPSTREAM_PIN=PASS"

$branchExists = Invoke-Git -AllowFailure -Arguments @("-C", $Workspace, "show-ref", "--verify", "--quiet", ("refs/heads/{0}" -f $OrionBranch))
if ($branchExists.ExitCode -eq 0) {
    Invoke-Git -Arguments @("-C", $Workspace, "switch", $OrionBranch) | Out-Null
}
else {
    Invoke-Git -Arguments @("-C", $Workspace, "switch", "--create", $OrionBranch, $UpstreamCommit) | Out-Null
}
Write-Host ("P4_01R2_BRANCH={0}" -f $OrionBranch)
Write-Host "P4_01R2_BRANCH_READY=PASS"

$licensePath = Join-Path -Path $Workspace -ChildPath "LICENSE"
if (-not (Test-Path -LiteralPath $licensePath -PathType Leaf)) {
    throw "Upstream LICENSE file is missing."
}
$licenseText = [System.IO.File]::ReadAllText($licensePath)
if ((-not $licenseText.Contains("MIT License")) -or
    (-not $licenseText.Contains("Copyright (c) 2026 Chris Lassiter"))) {
    throw "Upstream MIT attribution does not match the approved baseline."
}
Write-Host "P4_01R2_LICENSE_PRESERVED=PASS"

$hudPath = Join-Path -Path $Workspace -ChildPath "server\hud\index.html"
if (-not (Test-Path -LiteralPath $hudPath -PathType Leaf)) {
    throw "Pinned upstream HUD not found at server\hud\index.html."
}

$hud = [System.IO.File]::ReadAllText($hudPath)
$replacements = @(
    @("<title>JARVIS</title>", "<title>ORION</title>", "page title")
    @('<meta name="apple-mobile-web-app-title" content="JARVIS">', '<meta name="apple-mobile-web-app-title" content="ORION">', "mobile app title")
    @('<div id="bootLogo">J.A.R.V.I.S</div>', '<div id="bootLogo">ORION</div>', "boot logo")
    @('<div id="bootSub">HERMES NEURAL INTERFACE</div>', '<div id="bootSub">HERMES + iai PERSONAL COMPANION</div>', "boot subtitle")
    @('<h1>J.A.R.V.I.S</h1>', '<h1>ORION</h1>', "HUD header")
    @('<div class="sub">HERMES AGENT INTERFACE &nbsp;//&nbsp; <span id="connState">LINK DOWN</span></div>', '<div class="sub">PERSONAL AI COMPANION &nbsp;//&nbsp; HERMES + iai &nbsp;//&nbsp; <span id="connState">LINK DOWN</span></div>', "HUD subtitle")
    @('<div class="kv"><span>Conversation</span><b>jarvis-main</b></div>', '<div class="kv"><span>Conversation</span><b>orion-main</b></div>', "conversation label")
    @('<div class="kv"><span>Memory scope</span><b>jarvis:user:main</b></div>', '<div class="kv"><span>Memory scope</span><b>orion:user:main</b></div>', "memory scope label")
    @('const CONV = "jarvis-main";', 'const CONV = "orion-main";', "HUD conversation constant")
)

foreach ($item in $replacements) {
    $hud = Replace-LiteralOrVerify -Text $hud -Old $item[0] -New $item[1] -Label $item[2]
}

[System.IO.File]::WriteAllText($hudPath, $hud, [System.Text.UTF8Encoding]::new($false))
Write-Host "P4_01R2_VISIBLE_ORION_BRANDING=PASS"

$upstreamConfigPath = Join-Path -Path $Workspace -ChildPath "server\config\server.example.yaml"
$orionConfigPath = Join-Path -Path $Workspace -ChildPath "server\config\server.orion.example.yaml"
if (-not (Test-Path -LiteralPath $upstreamConfigPath -PathType Leaf)) {
    throw "Upstream server example config is missing."
}

$config = [System.IO.File]::ReadAllText($upstreamConfigPath)
$config = $config.Replace("conversation: jarvis-main", "conversation: orion-main")
$config = $config.Replace("session_key: jarvis:user:main", "session_key: orion:user:main")
$config = $config.Replace('voice_name: "Your chosen voice"', 'voice_name: "Orion voice"')
$config = $config.Replace("You are the spoken interface for the user's personal agent.", "You are the spoken interface for Orion, the user's personal AI companion.")

$configHeader = Join-Lines -Lines @(
    "# ORION MVP overlay derived from eadmin2/jarvis_ai."
    ("# Upstream commit: {0}" -f $UpstreamCommit)
    "#"
    "# IMPORTANT:"
    "# - Hermes remains the agent runtime."
    "# - iai remains Orion's authoritative memory engine."
    "# - This file does not configure a second memory system."
    "# - JARVIS_HUD_TOKEN remains an upstream-compatible internal environment variable name for now."
    "# - User-facing product identity is Orion."
    "#"
)

[System.IO.File]::WriteAllText(
    $orionConfigPath,
    ($configHeader + $config),
    [System.Text.UTF8Encoding]::new($false)
)
Write-Host "P4_01R2_ORION_CONFIG_OVERLAY=PASS"

$manifestPath = Join-Path -Path $Workspace -ChildPath "ORION-UPSTREAM.md"
$manifest = Join-Lines -Lines @(
    "# Orion HUD Upstream Baseline"
    ""
    "Orion uses eadmin2/jarvis_ai as the upstream HUD, voice, and orchestration application baseline."
    ""
    ("- Upstream repository: {0}" -f $UpstreamUrl)
    ("- Pinned upstream commit: {0}" -f $UpstreamCommit)
    "- Upstream license: MIT"
    "- Upstream copyright retained in LICENSE"
    ("- Orion fork: {0}" -f $ForkUrl)
    ("- Orion adaptation branch: {0}" -f $OrionBranch)
    ""
    "## Orion intent boundaries"
    ""
    "The upstream application is adopted for its Hermes-native HUD, voice pipeline, typed chat,"
    "live agent activity, STOP and barge-in behavior, approval-event UX, media panels, and local"
    "browser control surface."
    ""
    "Orion does not adopt any memory architecture that conflicts with the accepted Orion memory system."
    "iai remains the authoritative memory and semantic-recall engine. Obsidian remains the authoritative"
    "human-facing vault. Orion's accepted inbox, destination recommendation, approval broker, and recovery"
    "controls remain the document-management path."
    ""
    "P4-01 Revised changes only user-facing HUD branding and an Orion config overlay."
    "It does not modify server/server.py, the Hermes protocol implementation, iai, the accepted Orion vault"
    "services, or runtime secrets."
    ""
    "Internal upstream compatibility names may remain where renaming them would create unnecessary divergence."
    "User-facing product identity is Orion."
)

[System.IO.File]::WriteAllText($manifestPath, $manifest, [System.Text.UTF8Encoding]::new($false))
Write-Host "P4_01R2_UPSTREAM_MANIFEST=PASS"

Invoke-Git -Arguments @("-C", $Workspace, "add", "--", "server/hud/index.html", "server/config/server.orion.example.yaml", "ORION-UPSTREAM.md") | Out-Null

$staged = Invoke-Git -AllowFailure -Arguments @("-C", $Workspace, "diff", "--cached", "--quiet")
if ($staged.ExitCode -eq 1) {
    Invoke-Git -Arguments @(
        "-C", $Workspace,
        "-c", "user.name=Orion Bootstrap",
        "-c", "user.email=orion@local.invalid",
        "commit", "-m", "orion: adopt pinned jarvis HUD baseline"
    ) | Out-Null
}
elseif ($staged.ExitCode -ne 0) {
    throw "Could not determine staged Git state."
}

$deltaText = (Invoke-Git -Arguments @("-C", $Workspace, "diff", "--name-only", ("{0}..HEAD" -f $UpstreamCommit))).Text
$deltaFiles = @($deltaText -split "`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
$allowedDelta = @(
    "ORION-UPSTREAM.md"
    "server/config/server.orion.example.yaml"
    "server/hud/index.html"
)
$unexpected = @($deltaFiles | Where-Object { $_ -notin $allowedDelta })
if ($unexpected.Count -gt 0) {
    throw ("Unexpected Orion baseline changes detected: {0}" -f ($unexpected -join ", "))
}
foreach ($expectedFile in $allowedDelta) {
    if ($deltaFiles -notcontains $expectedFile) {
        throw ("Expected Orion adaptation file is missing from the branch delta: {0}" -f $expectedFile)
    }
}
Write-Host ("P4_01R2_DELTA_FILES={0}" -f ($deltaFiles -join ","))
Write-Host "P4_01R2_UPSTREAM_DELTA_BOUNDED=PASS"

$status = (Invoke-Git -Arguments @("-C", $Workspace, "status", "--porcelain")).Text
if (-not [string]::IsNullOrWhiteSpace($status)) {
    throw ("Workspace is not clean after the bounded commit:`n{0}" -f $status)
}

Invoke-Git -Arguments @("-C", $Workspace, "push", "--set-upstream", "origin", $OrionBranch) | Out-Null

$head = (Invoke-Git -Arguments @("-C", $Workspace, "rev-parse", "HEAD")).Text
$remoteBranch = Invoke-Git -Arguments @("ls-remote", "--heads", $ForkUrl, ("refs/heads/{0}" -f $OrionBranch))
if (-not $remoteBranch.Text.StartsWith($head, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Remote Orion branch does not match the local committed HEAD."
}
Write-Host ("P4_01R2_LOCAL_HEAD={0}" -f $head)
Write-Host "P4_01R2_CODE_PUSHED_TO_FORK=PASS"

Write-Host ""
Write-Host ("P4_01R2_WORKSPACE={0}" -f $Workspace)
Write-Host "P4_01R2_NO_SERVER_CORE_CHANGE=PASS"
Write-Host "P4_01R2_IAI_MEMORY_INTENT_PRESERVED=PASS"
Write-Host "P4_01_REVISED_FORK_ADOPTION=PASS"
