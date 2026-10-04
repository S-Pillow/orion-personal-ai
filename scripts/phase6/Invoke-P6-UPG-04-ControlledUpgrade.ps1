param(
    [switch]$Execute,
    [string]$AuthorizationToken = "",
    [string]$OrionRepo = "D:\Orion\orion-personal-ai",
    [string]$HermesHome = "$env:LOCALAPPDATA\hermes",
    [string]$CompanionHome = "$env:LOCALAPPDATA\hermes\profiles\companion",
    [string]$InstalledHermesRoot = "$env:LOCALAPPDATA\hermes\hermes-agent",
    [int]$GatewayPort = 8642,
    [switch]$AllowEmergencyForceStop
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RequiredAuthorizationToken = "P6-UPG-04-PRODUCTION-UPGRADE"
$TargetCommit = "f97608f178d1ffeca59860195ab7da295f7c8e5f"
$TargetBranch = "main"
$TargetTag = "v2026.9.24"
$ExpectedArtifactHash = "21edb9cf49eb6e2724852dc090f755cf38564db5026ab4d0b3814f34c0b355e4"
$ExpectedInstallerHash = "0a80dfeb7434229933bac32e73140d10086dff81bd84b156e71be9abc87cddf2"
$InstallerUrl = "https://raw.githubusercontent.com/NousResearch/hermes-agent/$TargetCommit/scripts/install.ps1"

$ExpectedRuntimeHashes = @{
    "agent/monitoring/cron_health.py" = "c1f187aa4685fbfafbf1090659fd3185544b9da95bb122c36727b2cb6369ae6a"
    "cron/error_classification.py" = "095a5482791088ab040c04446b5f3bb7d4aa3c5a95f4a1863329530d292f02eb"
    "cron/executions.py" = "990bac66f9d3b30e57cf598ba3099a11004edd893a3ab0f578ef713d7775180e"
    "cron/jobs.py" = "02a64327b8e0b41c03d6c43ca7f1f7c67a3b1f31e805f22ee30eb90b8d9f1a4a"
    "cron/scheduler_worker_env.py" = "18a2907456b8525eba7652f826c5812925773955484a07f6f665dfd42e388751"
}

$ExpectedCandidateStatus = @(
    " M agent/monitoring/cron_health.py",
    " M cron/executions.py",
    " M cron/jobs.py",
    " M cron/scheduler_worker_env.py",
    " M tests/cron/test_restart_safe_worker.py",
    "?? cron/error_classification.py"
) | Sort-Object

$RequiredPostColumns = @(
    "id", "job_id", "source", "process_id", "pid", "process_started_at",
    "status", "claimed_at", "started_at", "finished_at", "error",
    "scheduled_at", "delivery_outcome", "error_class",
    "handoff_pending", "handoff_started_at", "scheduled_instant"
)

function Stop-P6([string]$Message) {
    throw "STOP: $Message"
}

function Wait-GatewayListenerCount([int]$ExpectedCount, [int]$TimeoutSeconds = 60) {
    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $Listeners = @(Get-NetTCPConnection -LocalPort $GatewayPort -State Listen -ErrorAction SilentlyContinue)
        if ($Listeners.Count -eq $ExpectedCount) {
            return $Listeners
        }
        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $Deadline)
    return @(Get-NetTCPConnection -LocalPort $GatewayPort -State Listen -ErrorAction SilentlyContinue)
}

function Invoke-InstallerStage([string]$Installer, [string]$Stage, [string]$Home) {
    Write-Host "P6_UPG_04_INSTALLER_STAGE_BEGIN=$Stage"
    $Args = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $Installer,
        "-Stage", $Stage,
        "-NonInteractive",
        "-HermesHome", $Home,
        "-InstallDir", $InstalledHermesRoot,
        "-Branch", $TargetBranch,
        "-Commit", $TargetCommit,
        "-ForceCommit"
    )
    & powershell.exe @Args
    if ($LASTEXITCODE -ne 0) {
        Stop-P6 "official Hermes installer stage failed: $Stage"
    }
    Write-Host "P6_UPG_04_INSTALLER_STAGE_PASS=$Stage"
}

function Get-AppendedLogText([string]$Path, [long]$Offset) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return ""
    }
    $Stream = $null
    $Reader = $null
    try {
        $Stream = [IO.File]::Open(
            $Path,
            [IO.FileMode]::Open,
            [IO.FileAccess]::Read,
            [IO.FileShare]::ReadWrite
        )
        if ($Stream.Length -ge $Offset) {
            [void]$Stream.Seek($Offset, [IO.SeekOrigin]::Begin)
        }
        else {
            [void]$Stream.Seek(0, [IO.SeekOrigin]::Begin)
        }
        $Reader = New-Object IO.StreamReader($Stream)
        return $Reader.ReadToEnd()
    }
    catch {
        return ""
    }
    finally {
        if ($null -ne $Reader) { $Reader.Dispose() }
        elseif ($null -ne $Stream) { $Stream.Dispose() }
    }
}

function Get-LogOffsets([string[]]$Paths) {
    $Offsets = @{}
    foreach ($Path in $Paths) {
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            $Offsets[$Path] = [long](Get-Item -LiteralPath $Path).Length
        }
        else {
            $Offsets[$Path] = [long]0
        }
    }
    return $Offsets
}

function Get-StateDbPaths {
    $Paths = New-Object System.Collections.Generic.List[string]
    $Paths.Add((Join-Path $HermesHome "state.db"))
    $ProfilesRoot = Join-Path $HermesHome "profiles"
    if (Test-Path -LiteralPath $ProfilesRoot -PathType Container) {
        Get-ChildItem -LiteralPath $ProfilesRoot -Directory -ErrorAction SilentlyContinue |
            ForEach-Object { $Paths.Add((Join-Path $_.FullName "state.db")) }
    }
    return @($Paths | Select-Object -Unique)
}

$BackupRoot = $null
$BackupInstallRoot = $null
$BinBackup = $null
$MutationStarted = $false
$GatewayStopped = $false
$StateSafetyStop = $false
$OldGatewayPid = $null

function Invoke-P6Rollback {
    Write-Host "P6_UPG_04_ROLLBACK_BEGIN=true"

    try {
        $NewHermesExe = Join-Path $InstalledHermesRoot "venv\Scripts\hermes.exe"
        if (Test-Path -LiteralPath $NewHermesExe -PathType Leaf) {
            $PreviousEap = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            try {
                & $NewHermesExe gateway stop 2>&1 | ForEach-Object { Write-Host $_ }
            }
            catch {}
            finally {
                $ErrorActionPreference = $PreviousEap
            }
        }

        $Remaining = Wait-GatewayListenerCount -ExpectedCount 0 -TimeoutSeconds 20
        if ($Remaining.Count -ne 0) {
            Write-Host "P6_UPG_04_ROLLBACK_GRACEFUL_STOP_FAILED=true"
            if (-not $AllowEmergencyForceStop) {
                Write-Host "P6_UPG_04_ROLLBACK_BLOCKED_LIVE_LISTENER=true"
                throw "rollback cannot replace the installation while a gateway listener is still live; emergency force-stop was not separately authorized."
            }

            foreach ($Listener in $Remaining) {
                $Pid = [int]$Listener.OwningProcess
                $Proc = Get-CimInstance Win32_Process -Filter "ProcessId = $Pid"
                $LooksLikeHermesGateway = (
                    $null -ne $Proc -and
                    [string]$Proc.CommandLine -match "(?i)hermes_cli\.main.*gateway\s+run"
                )
                if (-not $LooksLikeHermesGateway) {
                    throw "emergency rollback refused to force-stop unverified listener owner PID $Pid."
                }
            }

            Write-Host "P6_UPG_04_EMERGENCY_FORCE_STOP_AUTHORIZED=true"
            foreach ($Listener in $Remaining) {
                Stop-Process -Id ([int]$Listener.OwningProcess) -Force -ErrorAction Stop
            }
            $Remaining = Wait-GatewayListenerCount -ExpectedCount 0 -TimeoutSeconds 10
            if ($Remaining.Count -ne 0) {
                throw "emergency force-stop did not release the gateway listener."
            }
        }

        if (Test-Path -LiteralPath $InstalledHermesRoot -PathType Container) {
            $FailedRoot = Join-Path $BackupRoot "failed-new-hermes-agent"
            if (Test-Path -LiteralPath $FailedRoot) {
                $FailedRoot = Join-Path $BackupRoot ("failed-new-hermes-agent-" + (Get-Date -Format "HHmmss"))
            }
            Move-Item -LiteralPath $InstalledHermesRoot -Destination $FailedRoot
            Write-Host "P6_UPG_04_ROLLBACK_FAILED_NEW_INSTALL=$FailedRoot"
        }

        if ($null -ne $BackupInstallRoot -and (Test-Path -LiteralPath $BackupInstallRoot -PathType Container)) {
            Move-Item -LiteralPath $BackupInstallRoot -Destination $InstalledHermesRoot
        }

        $BinRoot = Join-Path $HermesHome "bin"
        if ($null -ne $BinBackup -and (Test-Path -LiteralPath $BinBackup -PathType Container)) {
            if (Test-Path -LiteralPath $BinRoot -PathType Container) {
                $FailedBin = Join-Path $BackupRoot "failed-new-bin"
                if (-not (Test-Path -LiteralPath $FailedBin)) {
                    Move-Item -LiteralPath $BinRoot -Destination $FailedBin
                }
            }
            Copy-Item -LiteralPath $BinBackup -Destination $BinRoot -Recurse -Force
        }

        $OldHermesExe = Join-Path $InstalledHermesRoot "venv\Scripts\hermes.exe"
        if ($StateSafetyStop) {
            Write-Host "P6_UPG_04_STATE_SAFETY_HOLD=true"
            Write-Host "P6_UPG_04_ROLLBACK_GATEWAY_RESTORED=false"
            Write-Host "P6_UPG_04_STATE_RECOVERY_REQUIRES_OPERATOR_REVIEW=true"
        }
        elseif (Test-Path -LiteralPath $OldHermesExe -PathType Leaf) {
            $env:HERMES_HOME = $HermesHome
            $env:HERMES_NONINTERACTIVE = "1"
            $env:HERMES_GATEWAY_INSTALL_START_ON_LOGIN = "0"
            & $OldHermesExe gateway start
            $RollbackStartExit = $LASTEXITCODE
            $RollbackListeners = Wait-GatewayListenerCount -ExpectedCount 1 -TimeoutSeconds 60
            if ($RollbackStartExit -eq 0 -and $RollbackListeners.Count -eq 1) {
                Write-Host "P6_UPG_04_ROLLBACK_GATEWAY_RESTORED=true"
            }
            else {
                Write-Host "P6_UPG_04_ROLLBACK_GATEWAY_RESTORED=false"
            }
        }
        Write-Host "P6_UPG_04_ROLLBACK_COMPLETE=true"
    }
    catch {
        Write-Host "P6_UPG_04_ROLLBACK_COMPLETE=false"
        Write-Host "P6_UPG_04_ROLLBACK_ERROR_TYPE=$($_.Exception.GetType().Name)"
    }
}

Write-Host "P6_UPG_04_CONTROLLED_UPGRADE_PREPARED=true"
Write-Host "P6_UPG_04_TARGET=$TargetTag|$TargetCommit"
Write-Host "P6_UPG_04_HERMES_UPDATE_COMMAND_USED=false"

if (-not $Execute) {
    Write-Host "P6_UPG_04_EXECUTION_REQUESTED=false"
    Write-Host "P6_UPG_04_RESULT=NO_MUTATION_PREVIEW_ONLY"
    exit 0
}

if ($AuthorizationToken -ne $RequiredAuthorizationToken) {
    Stop-P6 "explicit P6-UPG-04 production authorization token is missing or incorrect."
}

if ($PSVersionTable.PSVersion.Major -ge 6 -and -not $IsWindows) {
    Stop-P6 "P6-UPG-04 production upgrade is Windows-only."
}

Set-Location $OrionRepo

$ClearancePath = Join-Path $OrionRepo "docs\phase6\p6-upg-04-warmup-clearance.json"
if (-not (Test-Path -LiteralPath $ClearancePath -PathType Leaf)) {
    Stop-P6 "vendor P1 #131145 has no qualified candidate clearance artifact. Production upgrade is NO-GO."
}
$Clearance = Get-Content -LiteralPath $ClearancePath -Raw | ConvertFrom-Json
$AllowedClearanceSources = @("upstream_merged_commit", "stable_release")
$ClearanceValid = (
    $Clearance.schema -eq 1 -and
    $Clearance.issue -eq 131145 -and
    $Clearance.status -eq "qualified_fix_included" -and
    $Clearance.candidate_artifact_sha256 -eq $ExpectedArtifactHash -and
    [string]$Clearance.vendor_fix.source -in $AllowedClearanceSources -and
    -not [string]::IsNullOrWhiteSpace([string]$Clearance.vendor_fix.reference) -and
    -not [string]::IsNullOrWhiteSpace([string]$Clearance.qualification.orion_commit) -and
    -not [string]::IsNullOrWhiteSpace([string]$Clearance.qualification.evidence)
)
if (-not $ClearanceValid) {
    Stop-P6 "vendor warm-up clearance artifact is invalid, incomplete, or does not bind to this candidate."
}
Write-Host "P6_UPG_04_VENDOR_CLEARANCE=PASS"

$Preflight = Join-Path $OrionRepo "scripts\phase6\Invoke-P6-UPG-04-Preflight.ps1"
$StateGuard = Join-Path $OrionRepo "scripts\phase6\p6-upg-04-state-guard.py"
$Artifact = Join-Path $OrionRepo "compat\hermes\v2026.9.24-orion-qualified-combined.patch"
foreach ($Required in @($Preflight, $StateGuard, $Artifact)) {
    if (-not (Test-Path -LiteralPath $Required -PathType Leaf)) {
        Stop-P6 "required P6-UPG-04 file missing: $Required"
    }
}

$PreflightArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $Preflight,
    "-OrionRepo", $OrionRepo,
    "-HermesHome", $HermesHome,
    "-CompanionHome", $CompanionHome,
    "-InstalledHermesRoot", $InstalledHermesRoot,
    "-GatewayPort", [string]$GatewayPort,
    "-VendorWarmupDisposition", "QUALIFIED_FIX_INCLUDED"
)
& powershell.exe @PreflightArgs
if ($LASTEXITCODE -ne 0) {
    Stop-P6 "read-only production preflight did not pass."
}

$ArtifactHash = (Get-FileHash -LiteralPath $Artifact -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ArtifactHash -ne $ExpectedArtifactHash) {
    Stop-P6 "combined compatibility artifact hash changed after preflight."
}

$WorkRoot = Join-Path $env:TEMP ("orion-p6-upg-04-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
$InstallerPath = Join-Path $WorkRoot "install-v2026.9.24.ps1"

Invoke-WebRequest -UseBasicParsing -Uri $InstallerUrl -OutFile $InstallerPath
$InstallerHash = (Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "P6_UPG_04_INSTALLER_SHA256=$InstallerHash"
if ($InstallerHash -ne $ExpectedInstallerHash) {
    Stop-P6 "downloaded exact-target installer hash mismatch."
}
Write-Host "P6_UPG_04_EXACT_TARGET_INSTALLER=PASS"

$PreListeners = @(Get-NetTCPConnection -LocalPort $GatewayPort -State Listen -ErrorAction SilentlyContinue)
if ($PreListeners.Count -ne 1) {
    Stop-P6 "gateway listener changed after preflight."
}
$OldGatewayPid = [int]$PreListeners[0].OwningProcess

$LogPaths = @(
    (Join-Path $HermesHome "logs\gateway.log"),
    (Join-Path $HermesHome "logs\gateway-error.log"),
    (Join-Path $HermesHome "logs\agent.log"),
    (Join-Path $HermesHome "logs\errors.log")
)
$LogOffsets = Get-LogOffsets $LogPaths

$OldHermesExe = Join-Path $InstalledHermesRoot "venv\Scripts\hermes.exe"
$OldPython = Join-Path $InstalledHermesRoot "venv\Scripts\python.exe"

$GatewayStatePath = Join-Path $HermesHome "gateway_state.json"
if (-not (Test-Path -LiteralPath $GatewayStatePath -PathType Leaf)) {
    Stop-P6 "gateway_state.json disappeared after preflight; do not stop the gateway."
}
try {
    $GatewayRuntime = Get-Content -LiteralPath $GatewayStatePath -Raw | ConvertFrom-Json
    $ActiveAgentsNow = [int]($GatewayRuntime.active_agents)
    $ActiveWorkNow = @($GatewayRuntime.active_work | Where-Object { $null -ne $_ }).Count
}
catch {
    Stop-P6 "gateway_state.json became unreadable after preflight; do not stop the gateway."
}
Write-Host "P6_UPG_04_PRESTOP_ACTIVE_AGENTS=$ActiveAgentsNow"
Write-Host "P6_UPG_04_PRESTOP_ACTIVE_WORK_COUNT=$ActiveWorkNow"
if ($ActiveAgentsNow -ne 0 -or $ActiveWorkNow -ne 0) {
    Stop-P6 "gateway became busy after preflight; defer the upgrade."
}
Write-Host "P6_UPG_04_PRESTOP_IDLE_RECHECK=PASS"

Write-Host "P6_UPG_04_GATEWAY_STOP_BEGIN=true"
$env:HERMES_HOME = $HermesHome
$env:HERMES_NONINTERACTIVE = "1"
$env:HERMES_GATEWAY_INSTALL_START_ON_LOGIN = "0"
& $OldHermesExe gateway stop
$StopExit = $LASTEXITCODE
$AfterStop = Wait-GatewayListenerCount -ExpectedCount 0 -TimeoutSeconds 45
if ($StopExit -ne 0 -or $AfterStop.Count -ne 0) {
    Write-Host "P6_UPG_04_GATEWAY_STOP_PASS=false"
    if ($AfterStop.Count -eq 0) {
        & $OldHermesExe gateway start
        [void](Wait-GatewayListenerCount -ExpectedCount 1 -TimeoutSeconds 60)
    }
    Stop-P6 "old gateway did not stop cleanly; source installation was not changed."
}
Write-Host "P6_UPG_04_GATEWAY_STOP_PASS=true"
$GatewayStopped = $true

try {
foreach ($Db in @(Get-StateDbPaths)) {
    & $OldPython -B $StateGuard --mode sqlite-integrity --db $Db
    if ($LASTEXITCODE -ne 0) {
        $StateSafetyStop = $true
        Stop-P6 "offline pre-upgrade SQLite integrity check failed; installation was not changed and the gateway will remain stopped for state review."
    }
}
Write-Host "P6_UPG_04_OFFLINE_PREUPGRADE_SQLITE=PASS"

$BackupBase = Join-Path $env:LOCALAPPDATA "orion-hermes-upgrade-backups"
New-Item -ItemType Directory -Force -Path $BackupBase | Out-Null
$BackupRoot = Join-Path $BackupBase ("p6-upg-04-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
if (Test-Path -LiteralPath $BackupRoot) {
    Stop-P6 "backup destination already exists: $BackupRoot"
}
New-Item -ItemType Directory -Path $BackupRoot | Out-Null
$BackupInstallRoot = Join-Path $BackupRoot "hermes-agent-v0.20.6"
$BinRoot = Join-Path $HermesHome "bin"
$BinBackup = Join-Path $BackupRoot "bin"

if (Test-Path -LiteralPath $BinRoot -PathType Container) {
    Copy-Item -LiteralPath $BinRoot -Destination $BinBackup -Recurse
}

$StateBackupRoot = Join-Path $BackupRoot "state-db"
New-Item -ItemType Directory -Path $StateBackupRoot | Out-Null
$StateBackupIndex = 0
foreach ($Db in @(Get-StateDbPaths)) {
    if (-not (Test-Path -LiteralPath $Db -PathType Leaf)) {
        continue
    }
    $StateBackupIndex += 1
    $BackupDb = Join-Path $StateBackupRoot ("state-$StateBackupIndex.db")
    & $OldPython -B $StateGuard --mode sqlite-backup --db $Db --out $BackupDb
    if ($LASTEXITCODE -ne 0) {
        Stop-P6 "verified offline SQLite backup failed; installation was not changed."
    }
}
Write-Host "P6_UPG_04_OFFLINE_STATE_BACKUPS=$StateBackupIndex"
Write-Host "P6_UPG_04_BACKUP_ROOT=$BackupRoot"

    Move-Item -LiteralPath $InstalledHermesRoot -Destination $BackupInstallRoot
    $MutationStarted = $true
    Write-Host "P6_UPG_04_OLD_INSTALL_PRESERVED=PASS"

    Invoke-InstallerStage -Installer $InstallerPath -Stage "repository" -Home $HermesHome

    git -C $InstalledHermesRoot config core.autocrlf false
    if ($LASTEXITCODE -ne 0) { Stop-P6 "failed to pin core.autocrlf=false on fresh target." }
    git -C $InstalledHermesRoot -c core.autocrlf=false checkout --force $TargetCommit
    if ($LASTEXITCODE -ne 0) { Stop-P6 "failed to normalize exact target checkout." }

    $NewHead = (git -C $InstalledHermesRoot rev-parse HEAD).Trim()
    if ($NewHead -ne $TargetCommit) {
        Stop-P6 "fresh target HEAD does not equal exact v0.21.5 commit."
    }

    git -C $InstalledHermesRoot apply --check $Artifact
    if ($LASTEXITCODE -ne 0) { Stop-P6 "combined qualified artifact does not apply to fresh target." }
    git -C $InstalledHermesRoot apply $Artifact
    if ($LASTEXITCODE -ne 0) { Stop-P6 "failed to apply combined qualified artifact." }
    git -C $InstalledHermesRoot diff --check
    if ($LASTEXITCODE -ne 0) { Stop-P6 "patched source failed git diff --check." }

    $CandidateStatus = @(
        git -C $InstalledHermesRoot status --porcelain=v1 --untracked-files=all |
            ForEach-Object { [string]$_ } |
            Sort-Object
    )
    $CandidateStatusDiff = @(Compare-Object -ReferenceObject $ExpectedCandidateStatus -DifferenceObject $CandidateStatus)
    if ($CandidateStatusDiff.Count -ne 0) {
        Write-Host "P6_UPG_04_CANDIDATE_STATUS_MISMATCH_BEGIN"
        $CandidateStatus | ForEach-Object { Write-Host $_ }
        Write-Host "P6_UPG_04_CANDIDATE_STATUS_MISMATCH_END"
        Stop-P6 "patched candidate dirty set differs from the qualified artifact."
    }

    foreach ($Relative in $ExpectedRuntimeHashes.Keys) {
        $Path = Join-Path $InstalledHermesRoot $Relative
        $ActualHash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($ActualHash -ne $ExpectedRuntimeHashes[$Relative]) {
            Stop-P6 "patched runtime source hash mismatch: $Relative"
        }
    }
    Write-Host "P6_UPG_04_PATCHED_SOURCE=PASS"

    foreach ($Stage in @("python", "venv", "dependencies", "node-deps")) {
        Invoke-InstallerStage -Installer $InstallerPath -Stage $Stage -Home $HermesHome
    }

    Invoke-InstallerStage -Installer $InstallerPath -Stage "platform-sdks" -Home $HermesHome
    Invoke-InstallerStage -Installer $InstallerPath -Stage "platform-sdks" -Home $CompanionHome
    Invoke-InstallerStage -Installer $InstallerPath -Stage "path" -Home $HermesHome
    Invoke-InstallerStage -Installer $InstallerPath -Stage "bootstrap-marker" -Home $HermesHome

    $NewPython = Join-Path $InstalledHermesRoot "venv\Scripts\python.exe"
    $NewHermesExe = Join-Path $InstalledHermesRoot "venv\Scripts\hermes.exe"
    foreach ($Path in @($NewPython, $NewHermesExe)) {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            Stop-P6 "new Hermes runtime missing after official installer stages: $Path"
        }
    }

    & $NewPython -B -c "import croniter, ruamel.yaml, cron.scheduler, dotenv, openai, rich, prompt_toolkit; print('P6_UPG_04_NEW_RUNTIME_IMPORTS=PASS')"
    if ($LASTEXITCODE -ne 0) {
        Stop-P6 "new Hermes runtime import gate failed."
    }

    @(& $NewHermesExe --version 2>&1) | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) {
        Stop-P6 "new Hermes version command failed."
    }
    Write-Host "P6_UPG_04_NEW_VERSION_COMMAND=PASS"

    $env:HERMES_HOME = $HermesHome
    $env:HERMES_NONINTERACTIVE = "1"
    $env:HERMES_GATEWAY_INSTALL_START_ON_LOGIN = "0"

    Write-Host "P6_UPG_04_GATEWAY_START_BEGIN=true"
    & $NewHermesExe gateway start
    if ($LASTEXITCODE -ne 0) {
        Stop-P6 "new gateway start command failed."
    }

    $NewListeners = Wait-GatewayListenerCount -ExpectedCount 1 -TimeoutSeconds 60
    if ($NewListeners.Count -ne 1) {
        Stop-P6 "new gateway did not return with exactly one listener."
    }
    $NewGatewayPid = [int]$NewListeners[0].OwningProcess
    if ($NewGatewayPid -eq $OldGatewayPid) {
        Stop-P6 "gateway PID did not change across controlled upgrade."
    }
    Write-Host "P6_UPG_04_NEW_GATEWAY_PID=$NewGatewayPid"

    & $NewHermesExe gateway status
    if ($LASTEXITCODE -ne 0) {
        Stop-P6 "gateway status failed after restart."
    }
    Write-Host "P6_UPG_04_GATEWAY_STATUS=PASS"

    $GatewayProcesses = @(
        Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
            Where-Object { [string]$_.CommandLine -match "(?i)hermes_cli\.main.*gateway\s+run" }
    )
    Write-Host "P6_UPG_04_GATEWAY_PROCESS_COUNT=$($GatewayProcesses.Count)"
    if ($GatewayProcesses.Count -ne 1) {
        Stop-P6 "duplicate or missing Hermes gateway process detected."
    }

    $PendingMarkers = @()
    $InstallStateRoot = Join-Path $HermesHome "installs"
    if (Test-Path -LiteralPath $InstallStateRoot -PathType Container) {
        $PendingMarkers = @(
            Get-ChildItem -LiteralPath $InstallStateRoot -Filter "source-completion-pending" -File -Recurse -ErrorAction SilentlyContinue
        )
    }
    if ($PendingMarkers.Count -ne 0) {
        Stop-P6 "source-completion-pending marker appeared after upgrade."
    }

    foreach ($Db in @(Get-StateDbPaths)) {
        & $NewPython -B $StateGuard --mode sqlite-integrity --db $Db
        if ($LASTEXITCODE -ne 0) {
            $StateSafetyStop = $true
            Stop-P6 "post-restart SQLite integrity check failed; fail closed and do not restart against unverified state."
        }
    }
    Write-Host "P6_UPG_04_POSTRESTART_SQLITE=PASS"

    $StateProbe = Join-Path $OrionRepo "scripts\phase6\p6-04-production-state-probe.py"
    $PostState = @(& $NewPython -B $StateProbe --companion-home $CompanionHome)
    if ($LASTEXITCODE -ne 0) {
        Stop-P6 "post-upgrade cron state probe failed."
    }
    $PostRowsLine = [string]($PostState | Where-Object { $_ -like "P6_04_PROD_STATE_EXECUTION_ROWS=*" })
    $PostJobsLine = [string]($PostState | Where-Object { $_ -like "P6_04_PROD_STATE_JOB_COUNT=*" })
    $PostColumnsLine = [string]($PostState | Where-Object { $_ -like "P6_04_PROD_STATE_EXECUTION_COLUMNS=*" })
    if (-not $PostRowsLine -or -not $PostJobsLine -or -not $PostColumnsLine) {
        Stop-P6 "post-upgrade cron state probe output is incomplete."
    }
    $PostRows = [int]$PostRowsLine.Split("=")[1]
    $PostJobs = [int]$PostJobsLine.Split("=")[1]
    $PostColumns = @($PostColumnsLine.Substring($PostColumnsLine.IndexOf("=") + 1).Split(","))
    if ($PostJobs -ne 0 -or $PostRows -ne 0) {
        $StateSafetyStop = $true
        Stop-P6 "cron logical counts changed across upgrade; fail closed for state review."
    }
    foreach ($Column in $RequiredPostColumns) {
        if ($Column -notin $PostColumns) {
            $StateSafetyStop = $true
            Stop-P6 "required post-upgrade execution column missing: $Column"
        }
    }
    Write-Host "P6_UPG_04_CRON_STATE_PRESERVED=PASS"

    $HeartbeatPath = Join-Path $CompanionHome "cron\ticker_heartbeat"
    $HeartbeatBefore = $null
    if (Test-Path -LiteralPath $HeartbeatPath -PathType Leaf) {
        [double]$HeartbeatBefore = (Get-Content -LiteralPath $HeartbeatPath -Raw).Trim()
    }
    $HeartbeatDeadline = (Get-Date).AddSeconds(80)
    $HeartbeatAdvanced = $false
    do {
        Start-Sleep -Seconds 5
        if (Test-Path -LiteralPath $HeartbeatPath -PathType Leaf) {
            [double]$HeartbeatNow = (Get-Content -LiteralPath $HeartbeatPath -Raw).Trim()
            if ($null -eq $HeartbeatBefore -or $HeartbeatNow -gt $HeartbeatBefore) {
                $HeartbeatAdvanced = $true
                break
            }
        }
    } while ((Get-Date) -lt $HeartbeatDeadline)
    if (-not $HeartbeatAdvanced) {
        Stop-P6 "cron ticker heartbeat did not advance after gateway restart."
    }
    Write-Host "P6_UPG_04_TICKER_HEARTBEAT_ADVANCED=PASS"

    $WarmupDeadline = (Get-Date).AddSeconds(45)
    $WarmupComplete = $false
    $WarmupTimeoutSeen = $false
    do {
        foreach ($LogPath in $LogPaths) {
            $Chunk = Get-AppendedLogText -Path $LogPath -Offset ([long]$LogOffsets[$LogPath])
            if ($Chunk -match "Turn machinery warmed in") {
                $WarmupComplete = $true
            }
            if ($Chunk -match "opening inbound gate anyway") {
                $WarmupTimeoutSeen = $true
            }
        }
        if ($WarmupComplete -or $WarmupTimeoutSeen) { break }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $WarmupDeadline)

    Write-Host "P6_UPG_04_WARMUP_COMPLETE=$($WarmupComplete.ToString().ToLowerInvariant())"
    Write-Host "P6_UPG_04_WARMUP_TIMEOUT_SEEN=$($WarmupTimeoutSeen.ToString().ToLowerInvariant())"
    if (-not $WarmupComplete -or $WarmupTimeoutSeen) {
        Stop-P6 "gateway warm-up acceptance failed."
    }

    Write-Host "P6_UPG_04_POSTUPGRADE_ACCEPTANCE=PASS"
    Write-Host "P6_UPG_04_ROLLBACK_BACKUP_RETAINED=$BackupRoot"
    Write-Host "P6_UPG_04_VERDICT=PASS"
    $MutationStarted = $false
    $GatewayStopped = $false
}
catch {
    $Failure = $_
    Write-Host "P6_UPG_04_FAILURE_TYPE=$($Failure.Exception.GetType().Name)"
    if ($MutationStarted) {
        Invoke-P6Rollback
    }
    elseif ($GatewayStopped) {
        if ($StateSafetyStop) {
            Write-Host "P6_UPG_04_STATE_SAFETY_HOLD=true"
            Write-Host "P6_UPG_04_PREMUTATION_GATEWAY_RESTORED=false"
            Write-Host "P6_UPG_04_STATE_RECOVERY_REQUIRES_OPERATOR_REVIEW=true"
        }
        else {
            try {
                $env:HERMES_HOME = $HermesHome
                $env:HERMES_NONINTERACTIVE = "1"
                $env:HERMES_GATEWAY_INSTALL_START_ON_LOGIN = "0"
                & $OldHermesExe gateway start
                $RestoreListeners = Wait-GatewayListenerCount -ExpectedCount 1 -TimeoutSeconds 60
                Write-Host "P6_UPG_04_PREMUTATION_GATEWAY_RESTORED=$($RestoreListeners.Count -eq 1)"
            }
            catch {
                Write-Host "P6_UPG_04_PREMUTATION_GATEWAY_RESTORED=false"
            }
        }
    }
    throw $Failure
}
