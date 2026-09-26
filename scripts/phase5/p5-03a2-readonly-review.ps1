[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ExpectedRepo = "D:\Orion\orion-personal-ai"
$ExpectedBranch = "feature/orion-phase5-p5-03a2-session-chat-approval-compat"
$ExpectedCandidateCommit = "74dfd2039d7bbff1e982f087a78827a48331097e"
$ExpectedHermesHead = "5fc308a70719a83cccdbba4c0e39c23f5a8239d5"
$ExpectedHermesSha = "ecfd6dd53610c24a81f078650a0b2b3e129478a50fdb5f353313fff6e12e3888"
$ExpectedPostSha = "e78422d1cf3788f1b9c8e06052470c23ebc4446e0a242992d35be8e5e6168288"

$ExpectedCandidateBlobs = [ordered]@{
    "docs/phase5/p5-03a2-session-chat-approval-compat.md" = "93702d462cb5c0f2aa01631c09f8ec47e99e06b6"
    "scripts/phase5/p5-03a2-readonly-review.py" = "1717e144f687d77af453d5fb268b5f7a677d168a"
    "scripts/phase5/p5-03a2-session-chat-approval-compat.ps1" = "e6609c4771a2849443f2364cc3175af2b93e13a2"
    "scripts/phase5/p5-03a2-session-chat-approval-compat.py" = "942d32dfac2d5dbc7811f5c2d93cc1cd6465d796"
}

$Repo = (Resolve-Path -LiteralPath $ExpectedRepo).Path
if ((Resolve-Path -LiteralPath (Get-Location).Path).Path -ne $Repo) {
    throw "STOP: run from exact Orion repo: $ExpectedRepo"
}

$Branch = (git branch --show-current).Trim()
$Head = (git rev-parse HEAD).Trim()
if ($Branch -notin @($ExpectedBranch, "main")) {
    throw "STOP: review gate must run from the P5-03A2 feature branch or main; observed: $Branch"
}

git merge-base --is-ancestor $ExpectedCandidateCommit HEAD 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "STOP: accepted P5-03A2 candidate commit is not an ancestor of HEAD."
}

$Actual = @(git status --porcelain=v1)
if ($Actual.Count -ne 0) {
    Write-Output "Observed Orion status:"
    $Actual
    throw "STOP: Orion worktree must be clean for committed-candidate review."
}

foreach ($Entry in $ExpectedCandidateBlobs.GetEnumerator()) {
    $ObservedBlob = (git rev-parse "HEAD:$($Entry.Key)" 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or $ObservedBlob -ne $Entry.Value) {
        throw "STOP: candidate file identity drift: $($Entry.Key) expected $($Entry.Value), observed $ObservedBlob"
    }
}

$HermesRoot = Join-Path $env:LOCALAPPDATA "hermes\hermes-agent"
$Target = Join-Path $HermesRoot "gateway\platforms\api_server.py"
$HermesPython = Join-Path $HermesRoot "venv\Scripts\python.exe"
$Patcher = Join-Path $Repo "scripts\phase5\p5-03a2-session-chat-approval-compat.py"
$Review = Join-Path $Repo "scripts\phase5\p5-03a2-readonly-review.py"

$HermesHead = (git -C $HermesRoot rev-parse HEAD).Trim()
if ($HermesHead -ne $ExpectedHermesHead) {
    throw "STOP: Hermes HEAD drift: $HermesHead"
}

$ExpectedDirty = @(
    " M gateway/platforms/api_server.py",
    "?? gateway/platforms/api_server.py.orion-p4-04a.bak",
    "?? gateway/platforms/api_server.py.orion-p4-04a.json"
) | Sort-Object
$BeforeDirty = @((git -C $HermesRoot status --porcelain=v1) | Sort-Object)
if ($BeforeDirty.Count -ne $ExpectedDirty.Count -or (Compare-Object $ExpectedDirty $BeforeDirty)) {
    throw "STOP: Hermes worktree is not the exact accepted P4-04A state."
}

$BeforeSha = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant()
if ($BeforeSha -ne $ExpectedHermesSha) {
    throw "STOP: Hermes api_server.py SHA drift: $BeforeSha"
}

$Listening = $false
try {
    $Listening = @(Get-NetTCPConnection -LocalPort 8642 -State Listen -ErrorAction SilentlyContinue).Count -gt 0
}
catch {
    $Listening = $false
}
if ($Listening) { throw "STOP: Hermes port 8642 is listening." }

if (-not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable("ORION_P5_MUTATION_MODE"))) {
    throw "STOP: ORION_P5_MUTATION_MODE is present."
}

Write-Output "P5_03A2_REVIEW_BRANCH=$Branch"
Write-Output "P5_03A2_REVIEW_HEAD=$Head"
Write-Output "P5_03A2_REVIEW_CANDIDATE_COMMIT=$ExpectedCandidateCommit"
Write-Output "P5_03A2_REVIEW_CANDIDATE_FILES=PINNED"
Write-Output "P5_03A2_REVIEW_HERMES_HEAD=$HermesHead"
Write-Output "P5_03A2_REVIEW_HERMES_PRE_SHA256=$BeforeSha"

& $HermesPython $Review --target $Target --patcher $Patcher
$ReviewExit = $LASTEXITCODE
Write-Output "P5_03A2_REVIEW_PYTHON_EXIT_CODE=$ReviewExit"
if ($ReviewExit -ne 0) {
    throw "STOP: P5-03A2 read-only Python review failed."
}

$AfterSha = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant()
$AfterDirty = @((git -C $HermesRoot status --porcelain=v1) | Sort-Object)
$AfterOrion = @((git status --porcelain=v1) | Sort-Object)

if ($AfterSha -ne $BeforeSha) {
    throw "STOP: installed Hermes source changed during read-only review."
}
if ($AfterDirty.Count -ne $BeforeDirty.Count -or (Compare-Object $BeforeDirty $AfterDirty)) {
    throw "STOP: Hermes worktree changed during read-only review."
}
if ($AfterOrion.Count -ne $Actual.Count -or (Compare-Object $Actual $AfterOrion)) {
    throw "STOP: Orion worktree changed during read-only review."
}

Write-Output "P5_03A2_REVIEW_HERMES_POST_SHA256=$AfterSha"
Write-Output "P5_03A2_REVIEW_HERMES_UNCHANGED=true"
Write-Output "P5_03A2_REVIEW_ORION_UNCHANGED=true"
Write-Output "P5_03A2_READONLY_REVIEW_WRAPPER=PASS"
