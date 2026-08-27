[CmdletBinding()]
param(
    [string]$HudWorkspace = "E:\Orion-Phase2\Orion-HUD",
    [string]$HermesContainer = "orion-iai-m5-c"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ExpectedHudBranch = "orion-mvp"
$ExpectedHudHead = "aeb0643f8119a4d4f8b78a950194e9778eea4af2"

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$AllowFailure
    )

    $saved = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $raw = & $FilePath @Arguments 2>&1
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $saved
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

function Test-LocalTcpPort {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [int]$TimeoutMs = 800
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) {
            return $false
        }
        $client.EndConnect($async)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Test-ContainerListeningPort {
    param(
        [Parameter(Mandatory = $true)][string]$Container,
        [Parameter(Mandatory = $true)][int]$Port
    )

    $hexPort = ("{0:X4}" -f $Port).ToUpperInvariant()
    $tcp = Invoke-Native -AllowFailure -FilePath "docker" -Arguments @(
        "exec",
        $Container,
        "cat",
        "/proc/net/tcp",
        "/proc/net/tcp6"
    )

    if ($tcp.ExitCode -ne 0) {
        return $false
    }

    foreach ($line in ($tcp.Text -split "`n")) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("sl ")) {
            continue
        }

        $parts = @($trimmed -split "\s+" | Where-Object { $_ })
        if ($parts.Count -lt 4) {
            continue
        }

        $local = [string]$parts[1]
        $state = [string]$parts[3]

        if ($state -ne "0A") {
            continue
        }

        $colon = $local.LastIndexOf(":")
        if ($colon -lt 0) {
            continue
        }

        $localPort = $local.Substring($colon + 1).ToUpperInvariant()
        if ($localPort -eq $hexPort) {
            return $true
        }
    }

    return $false
}

Write-Host "P4-02A v2 Orion runtime-fit discovery"
Write-Host "Read-only: no container recreation, no config writes, no secrets printed."
Write-Host ""

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is required but was not found in PATH."
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required but was not found in PATH."
}
Write-Host "P4_02A_V2_TOOLS_AVAILABLE=PASS"

if (-not (Test-Path -LiteralPath $HudWorkspace -PathType Container)) {
    throw ("Orion HUD workspace not found: {0}" -f $HudWorkspace)
}
if (-not (Test-Path -LiteralPath (Join-Path -Path $HudWorkspace -ChildPath ".git") -PathType Container)) {
    throw ("Orion HUD workspace is not a Git repository: {0}" -f $HudWorkspace)
}

$branch = (Invoke-Native -FilePath "git" -Arguments @("-C", $HudWorkspace, "branch", "--show-current")).Text
$head = (Invoke-Native -FilePath "git" -Arguments @("-C", $HudWorkspace, "rev-parse", "HEAD")).Text
$status = (Invoke-Native -FilePath "git" -Arguments @("-C", $HudWorkspace, "status", "--porcelain")).Text

if ($branch -ne $ExpectedHudBranch) {
    throw ("HUD branch mismatch. Expected {0}; found {1}" -f $ExpectedHudBranch, $branch)
}
if ($head -ne $ExpectedHudHead) {
    throw ("HUD HEAD mismatch. Expected {0}; found {1}" -f $ExpectedHudHead, $head)
}
if (-not [string]::IsNullOrWhiteSpace($status)) {
    throw ("HUD workspace has uncommitted changes. P4-02A v2 is discovery-only and will not proceed over a dirty tree.`n{0}" -f $status)
}

Write-Host "P4_02A_V2_HUD_WORKSPACE=PASS"
Write-Host ("P4_02A_V2_HUD_BRANCH={0}" -f $branch)
Write-Host ("P4_02A_V2_HUD_HEAD={0}" -f $head)
Write-Host "P4_02A_V2_HUD_WORKSPACE_CLEAN=PASS"

$runningNames = @((Invoke-Native -FilePath "docker" -Arguments @("ps", "--format", "{{.Names}}")).Text -split "`n" | Where-Object { $_ })
if ($runningNames -notcontains $HermesContainer) {
    throw ("Expected Hermes/iai container is not running: {0}" -f $HermesContainer)
}
Write-Host "P4_02A_V2_HERMES_CONTAINER_RUNNING=PASS"

$image = (Invoke-Native -FilePath "docker" -Arguments @("inspect", "--format", "{{.Config.Image}}", $HermesContainer)).Text
Write-Host ("P4_02A_V2_HERMES_IMAGE={0}" -f $image)

$portMap = Invoke-Native -AllowFailure -FilePath "docker" -Arguments @("port", $HermesContainer)
if (($portMap.ExitCode -eq 0) -and (-not [string]::IsNullOrWhiteSpace($portMap.Text))) {
    Write-Host ("P4_02A_V2_PUBLISHED_PORTS={0}" -f ($portMap.Text.Replace("`r", "").Replace("`n", ";")))
}
else {
    Write-Host "P4_02A_V2_PUBLISHED_PORTS=<none>"
}

$networkSummary = (Invoke-Native -FilePath "docker" -Arguments @(
    "inspect",
    "--format",
    "{{range `$k,`$v := .NetworkSettings.Networks}}{{`$k}}={{`$v.IPAddress}} {{end}}",
    $HermesContainer
)).Text
Write-Host ("P4_02A_V2_CONTAINER_NETWORKS={0}" -f $networkSummary)

# Read Linux socket tables directly to avoid nested command quoting.
# identify LISTEN state (0A) for the target ports.
$container8642 = Test-ContainerListeningPort -Container $HermesContainer -Port 8642
$container9119 = Test-ContainerListeningPort -Container $HermesContainer -Port 9119

Write-Host ("P4_02A_V2_CONTAINER_PORT_8642={0}" -f ($(if ($container8642) { "OPEN" } else { "CLOSED" })))
Write-Host ("P4_02A_V2_CONTAINER_PORT_9119={0}" -f ($(if ($container9119) { "OPEN" } else { "CLOSED" })))

$host8642 = Test-LocalTcpPort -Port 8642
$host9119 = Test-LocalTcpPort -Port 9119
$host4477 = Test-LocalTcpPort -Port 4477

Write-Host ("P4_02A_V2_HOST_PORT_8642={0}" -f ($(if ($host8642) { "OPEN" } else { "CLOSED" })))
Write-Host ("P4_02A_V2_HOST_PORT_9119={0}" -f ($(if ($host9119) { "OPEN" } else { "CLOSED" })))
Write-Host ("P4_02A_V2_HOST_PORT_4477={0}" -f ($(if ($host4477) { "OPEN" } else { "CLOSED" })))

$route = if ($host8642) {
    "host-local"
}
elseif ($container8642) {
    "container-only"
}
else {
    "not-listening"
}
Write-Host ("P4_02A_V2_HERMES_API_ROUTE={0}" -f $route)

$pythonCmd = Get-Command py -ErrorAction SilentlyContinue
if ($null -ne $pythonCmd) {
    $py = Invoke-Native -AllowFailure -FilePath "py" -Arguments @("-3", "--version")
    if ($py.ExitCode -eq 0) {
        Write-Host ("P4_02A_V2_HOST_PYTHON={0}" -f $py.Text)
    }
    else {
        Write-Host "P4_02A_V2_HOST_PYTHON=py-launcher-present-no-python3"
    }
}
else {
    $pythonExe = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $pythonExe) {
        $py = Invoke-Native -AllowFailure -FilePath "python" -Arguments @("--version")
        if ($py.ExitCode -eq 0) {
            Write-Host ("P4_02A_V2_HOST_PYTHON={0}" -f $py.Text)
        }
        else {
            Write-Host "P4_02A_V2_HOST_PYTHON=python-command-present-version-failed"
        }
    }
    else {
        Write-Host "P4_02A_V2_HOST_PYTHON=<not-found>"
    }
}

$configOverlay = Join-Path -Path $HudWorkspace -ChildPath "server\config\server.orion.example.yaml"
$serverFile = Join-Path -Path $HudWorkspace -ChildPath "server\server.py"
$hudFile = Join-Path -Path $HudWorkspace -ChildPath "server\hud\index.html"

foreach ($requiredPath in @($configOverlay, $serverFile, $hudFile)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw ("Required Orion HUD source file is missing: {0}" -f $requiredPath)
    }
}
Write-Host "P4_02A_V2_HUD_SOURCE_LAYOUT=PASS"

Write-Host ""
Write-Host "P4_02A_V2_NO_CONFIG_WRITE=PASS"
Write-Host "P4_02A_V2_NO_CONTAINER_CHANGE=PASS"
Write-Host "P4_02A_V2_NO_SECRET_OUTPUT=PASS"
Write-Host "P4_02A_V2_READ_ONLY_DISCOVERY=PASS"
Write-Host "P4_02A_V2_DISCOVERY=PASS"
