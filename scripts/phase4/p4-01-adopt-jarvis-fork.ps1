[CmdletBinding()]
param(
    [string]$Workspace = "E:\Orion-Phase2\Orion-HUD"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ForkUrl = "https://github.com/S-Pillow/jarvis_ai.git"
$UpstreamUrl = "https://github.com/eadmin2/jarvis_ai.git"
$UpstreamCommit = "88998de8369e9d36f6d434b5e01feb93fcf1c33f"
$OrionBranch = "orion-mvp"

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
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

    $text = (($raw | ForEach-Object { [string]$_ }) -join "`n").Trim()

    if (($code -ne 0) -and (-not $AllowFailure)) {
        throw ("Git failed with exit {0}: git {1}`n{2}" -f $code, ($Arguments -join " "), $text)
    }

    [pscustomobject]@{
        ExitCode = $code
        Text = $text
    }
}

function Replace-Or-Verify {
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
        throw ("Could not find either the upstream or Orion form for {0}." -f $Label)
    }

    return $Text.Replace($Old, $New)
}

Write-Host "P4-01 Revised v4 - repair and finish fork adoption"
Write-Host "This resumes the current Orion-HUD workspace without resetting it."
Write-Host ""

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is required but was not found in PATH."
}
Write-Host "P4_01R4_GIT_AVAILABLE=PASS"

if (-not (Test-Path -LiteralPath $Workspace -PathType Container)) {
    throw ("Workspace not found: {0}" -f $Workspace)
}
if (-not (Test-Path -LiteralPath (Join-Path -Path $Workspace -ChildPath ".git") -PathType Container)) {
    throw ("Workspace is not a Git repository: {0}" -f $Workspace)
}
Write-Host "P4_01R4_WORKSPACE_PRESENT=PASS"

$origin = (Invoke-Git -Arguments @("-C", $Workspace, "remote", "get-url", "origin")).Text
if ($origin -ne $ForkUrl) {
    throw ("Origin mismatch. Expected {0}; found {1}" -f $ForkUrl, $origin)
}
Write-Host "P4_01R4_ORIGIN_IS_FORK=PASS"

$upstream = (Invoke-Git -Arguments @("-C", $Workspace, "remote", "get-url", "upstream")).Text
if ($upstream -ne $UpstreamUrl) {
    throw ("Upstream mismatch. Expected {0}; found {1}" -f $UpstreamUrl, $upstream)
}
Write-Host "P4_01R4_UPSTREAM_REMOTE=PASS"

$branch = (Invoke-Git -Arguments @("-C", $Workspace, "branch", "--show-current")).Text
if ($branch -ne $OrionBranch) {
    throw ("Branch mismatch. Expected {0}; found {1}" -f $OrionBranch, $branch)
}
Write-Host "P4_01R4_BRANCH_READY=PASS"

$pinned = (Invoke-Git -Arguments @("-C", $Workspace, "rev-parse", $UpstreamCommit)).Text
if ($pinned -ne $UpstreamCommit) {
    throw ("Pinned commit mismatch. Expected {0}; found {1}" -f $UpstreamCommit, $pinned)
}
Write-Host "P4_01R4_UPSTREAM_PIN=PASS"

$allowedFiles = @(
    "ORION-UPSTREAM.md"
    "server/config/server.orion.example.yaml"
    "server/hud/index.html"
)

$localChanges = @()
foreach ($args in @(
    @("-C", $Workspace, "diff", "--name-only"),
    @("-C", $Workspace, "diff", "--cached", "--name-only"),
    @("-C", $Workspace, "ls-files", "--others", "--exclude-standard")
)) {
    $result = (Invoke-Git -Arguments $args).Text
    if (-not [string]::IsNullOrWhiteSpace($result)) {
        $localChanges += @($result -split "`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    }
}

$localChanges = @($localChanges | Sort-Object -Unique)
$unexpectedLocal = @($localChanges | Where-Object { $_ -notin $allowedFiles })
if ($unexpectedLocal.Count -gt 0) {
    throw ("Unexpected local changes are present: {0}" -f ($unexpectedLocal -join ", "))
}
Write-Host ("P4_01R4_EXISTING_CHANGE_SET={0}" -f ($(if ($localChanges.Count -eq 0) { "<clean>" } else { $localChanges -join "," })))
Write-Host "P4_01R4_EXISTING_CHANGES_BOUNDED=PASS"

$licensePath = Join-Path -Path $Workspace -ChildPath "LICENSE"
$hudPath = Join-Path -Path $Workspace -ChildPath "server\hud\index.html"
$upstreamConfigPath = Join-Path -Path $Workspace -ChildPath "server\config\server.example.yaml"
$orionConfigPath = Join-Path -Path $Workspace -ChildPath "server\config\server.orion.example.yaml"
$manifestPath = Join-Path -Path $Workspace -ChildPath "ORION-UPSTREAM.md"

if (-not (Test-Path -LiteralPath $licensePath -PathType Leaf)) {
    throw "LICENSE is missing."
}
$licenseText = [System.IO.File]::ReadAllText($licensePath)
if ((-not $licenseText.Contains("MIT License")) -or
    (-not $licenseText.Contains("Copyright (c) 2026 Chris Lassiter"))) {
    throw "MIT license attribution verification failed."
}
Write-Host "P4_01R4_LICENSE_PRESERVED=PASS"

if (-not (Test-Path -LiteralPath $hudPath -PathType Leaf)) {
    throw "HUD file is missing."
}

$hud = [System.IO.File]::ReadAllText($hudPath)
$hud = Replace-Or-Verify -Text $hud -Old "<title>JARVIS</title>" -New "<title>ORION</title>" -Label "page title"
$hud = Replace-Or-Verify -Text $hud -Old '<meta name="apple-mobile-web-app-title" content="JARVIS">' -New '<meta name="apple-mobile-web-app-title" content="ORION">' -Label "mobile app title"
$hud = Replace-Or-Verify -Text $hud -Old '<div id="bootLogo">J.A.R.V.I.S</div>' -New '<div id="bootLogo">ORION</div>' -Label "boot logo"
$hud = Replace-Or-Verify -Text $hud -Old '<div id="bootSub">HERMES NEURAL INTERFACE</div>' -New '<div id="bootSub">HERMES + iai PERSONAL COMPANION</div>' -Label "boot subtitle"
$hud = Replace-Or-Verify -Text $hud -Old '<h1>J.A.R.V.I.S</h1>' -New '<h1>ORION</h1>' -Label "HUD header"
$hud = Replace-Or-Verify -Text $hud -Old '<div class="sub">HERMES AGENT INTERFACE &nbsp;//&nbsp; <span id="connState">LINK DOWN</span></div>' -New '<div class="sub">PERSONAL AI COMPANION &nbsp;//&nbsp; HERMES + iai &nbsp;//&nbsp; <span id="connState">LINK DOWN</span></div>' -Label "HUD subtitle"
$hud = Replace-Or-Verify -Text $hud -Old '<div class="kv"><span>Conversation</span><b>jarvis-main</b></div>' -New '<div class="kv"><span>Conversation</span><b>orion-main</b></div>' -Label "conversation label"
$hud = Replace-Or-Verify -Text $hud -Old '<div class="kv"><span>Memory scope</span><b>jarvis:user:main</b></div>' -New '<div class="kv"><span>Memory scope</span><b>orion:user:main</b></div>' -Label "memory scope label"
$hud = Replace-Or-Verify -Text $hud -Old 'const CONV = "jarvis-main";' -New 'const CONV = "orion-main";' -Label "HUD conversation constant"

[System.IO.File]::WriteAllText($hudPath, $hud, [System.Text.UTF8Encoding]::new($true))

$verifyHud = [System.IO.File]::ReadAllText($hudPath)
foreach ($fragment in @(
    "<title>ORION</title>"
    '<meta name="apple-mobile-web-app-title" content="ORION">'
    '<div id="bootLogo">ORION</div>'
    '<h1>ORION</h1>'
    '<div class="kv"><span>Conversation</span><b>orion-main</b></div>'
    '<div class="kv"><span>Memory scope</span><b>orion:user:main</b></div>'
    'const CONV = "orion-main";'
)) {
    if (-not $verifyHud.Contains($fragment)) {
        throw ("HUD branding verification failed for: {0}" -f $fragment)
    }
}
Write-Host "P4_01R4_VISIBLE_ORION_BRANDING=PASS"

if (-not (Test-Path -LiteralPath $upstreamConfigPath -PathType Leaf)) {
    throw "Upstream config example is missing."
}

$config = [System.IO.File]::ReadAllText($upstreamConfigPath)
$config = $config.Replace("conversation: jarvis-main", "conversation: orion-main")
$config = $config.Replace("session_key: jarvis:user:main", "session_key: orion:user:main")
$config = $config.Replace('voice_name: "Your chosen voice"', 'voice_name: "Orion voice"')
$config = $config.Replace(
    "You are the spoken interface for the user's personal agent.",
    "You are the spoken interface for Orion, the user's personal AI companion."
)

$configLines = @(
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
    $config
)
$finalConfig = ($configLines -join [Environment]::NewLine)
[System.IO.File]::WriteAllText($orionConfigPath, $finalConfig, [System.Text.UTF8Encoding]::new($true))

$verifyConfig = [System.IO.File]::ReadAllText($orionConfigPath)
if ((-not $verifyConfig.Contains("conversation: orion-main")) -or
    (-not $verifyConfig.Contains("session_key: orion:user:main")) -or
    (-not $verifyConfig.Contains("iai remains Orion's authoritative memory engine."))) {
    throw "Orion config overlay verification failed."
}
Write-Host "P4_01R4_ORION_CONFIG_OVERLAY=PASS"

$manifestLines = @(
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
$manifest = ($manifestLines -join [Environment]::NewLine) + [Environment]::NewLine
[System.IO.File]::WriteAllText($manifestPath, $manifest, [System.Text.UTF8Encoding]::new($true))
Write-Host "P4_01R4_UPSTREAM_MANIFEST=PASS"

Invoke-Git -Arguments @("-C", $Workspace, "add", "--", "server/hud/index.html", "server/config/server.orion.example.yaml", "ORION-UPSTREAM.md") | Out-Null

$staged = Invoke-Git -AllowFailure -Arguments @("-C", $Workspace, "diff", "--cached", "--quiet")
if ($staged.ExitCode -eq 1) {
    $nameCheck = Invoke-Git -AllowFailure -Arguments @("-C", $Workspace, "config", "user.name")
    $emailCheck = Invoke-Git -AllowFailure -Arguments @("-C", $Workspace, "config", "user.email")

    if (($nameCheck.ExitCode -eq 0) -and ($emailCheck.ExitCode -eq 0) -and
        (-not [string]::IsNullOrWhiteSpace($nameCheck.Text)) -and
        (-not [string]::IsNullOrWhiteSpace($emailCheck.Text))) {
        Invoke-Git -Arguments @("-C", $Workspace, "commit", "-m", "orion: adopt pinned jarvis HUD baseline") | Out-Null
    }
    else {
        Invoke-Git -Arguments @(
            "-C", $Workspace,
            "-c", "user.name=Orion Bootstrap",
            "-c", "user.email=orion@local.invalid",
            "commit", "-m", "orion: adopt pinned jarvis HUD baseline"
        ) | Out-Null
    }
}
elseif ($staged.ExitCode -ne 0) {
    throw "Could not determine staged Git state."
}
Write-Host "P4_01R4_LOCAL_COMMIT_READY=PASS"

$deltaText = (Invoke-Git -Arguments @("-C", $Workspace, "diff", "--name-only", ("{0}..HEAD" -f $UpstreamCommit))).Text
$deltaFiles = @($deltaText -split "`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique)

foreach ($expectedFile in $allowedFiles) {
    if ($deltaFiles -notcontains $expectedFile) {
        throw ("Expected adaptation file missing from branch delta: {0}" -f $expectedFile)
    }
}
$unexpectedDelta = @($deltaFiles | Where-Object { $_ -notin $allowedFiles })
if ($unexpectedDelta.Count -gt 0) {
    throw ("Unexpected files in branch delta: {0}" -f ($unexpectedDelta -join ", "))
}
Write-Host ("P4_01R4_DELTA_FILES={0}" -f ($deltaFiles -join ","))
Write-Host "P4_01R4_UPSTREAM_DELTA_BOUNDED=PASS"

$status = (Invoke-Git -Arguments @("-C", $Workspace, "status", "--porcelain")).Text
if (-not [string]::IsNullOrWhiteSpace($status)) {
    throw ("Workspace is not clean after commit:`n{0}" -f $status)
}
Write-Host "P4_01R4_WORKSPACE_CLEAN=PASS"

Invoke-Git -Arguments @("-C", $Workspace, "push", "--set-upstream", "origin", $OrionBranch) | Out-Null

$head = (Invoke-Git -Arguments @("-C", $Workspace, "rev-parse", "HEAD")).Text
$remote = (Invoke-Git -Arguments @("ls-remote", "--heads", $ForkUrl, ("refs/heads/{0}" -f $OrionBranch))).Text
if (-not $remote.StartsWith($head, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Remote fork branch does not match local HEAD."
}
Write-Host ("P4_01R4_LOCAL_HEAD={0}" -f $head)
Write-Host "P4_01R4_CODE_PUSHED_TO_FORK=PASS"

Write-Host ""
Write-Host "P4_01R4_NO_SERVER_CORE_CHANGE=PASS"
Write-Host "P4_01R4_IAI_MEMORY_INTENT_PRESERVED=PASS"
Write-Host "P4_01_REVISED_FORK_ADOPTION=PASS"
