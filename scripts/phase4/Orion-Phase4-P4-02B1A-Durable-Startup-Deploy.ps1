[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Core = 'orion-iai-m5-c'
$Dashboard = 'orion-iai-dashboard'
$ExpectedCoreId = '86f1b8fb97532d791c529a9e6654a43e9c04245fb44d7c00678b2fc0a5509375'
$ExpectedCoreStartedAt = '2026-08-28T07:32:42.028908156Z'
$BaseImage = 'orion-hermes-iai:v2026.8.18-iai3.0.8-m5-extidle-b6d356e'
$ExpectedBaseImageId = 'sha256:db651747ed9e785fa839470d06535e37134a858e2d16077106f77ba6bd2d1517'
$SupervisedImage = 'orion-hermes-iai:v2026.8.18-iai3.0.8-m5-extidle-b6d356e-supervised'
$DataVolume = 'orion-iai-m5-data'
$ControlNetwork = 'orion-control-net'

$OrionRepo = 'E:\Orion-Phase2\orion-personal-ai-source'
$DurableBranchRef = 'origin/feature/p4-02b1a-durable-startup'
$DurableCommit = '20f6f252dbd407e8cdfec9457d9b43b2b6b2c8c6'
$DurableRef = $DurableCommit
$DockerfileRepoPath = 'build/orion-runtime/Dockerfile.07-iai-daemon-supervised'
$DaemonRunRepoPath = 'build/orion-runtime/s6/orion-iai-daemon/run'
$BridgeRepoPath = 'scripts/phase4/Orion-Phase4-P4-02B1A-Host-Idle-Bridge.ps1'
$TaskInstallerRepoPath = 'scripts/phase4/Install-Orion-Host-Idle-Bridge-Task.ps1'

$ProfileRoot = '/opt/data/profiles/companion'
$StoreRoot = '/opt/data/profiles/companion/.iai-mcp'
$SocketPath = '/opt/data/profiles/companion/.iai-mcp/.daemon.sock'
$IaiPython = '/opt/iai/venv/bin/python'
$IaiCli = '/opt/iai/venv/bin/iai-mcp'
$HermesCli = '/opt/hermes/.venv/bin/hermes'
$ExternalIdleContainerPath = '/orion-host-idle/host-idle.json'
$HostIdleDir = 'C:\HermesAgent\data\orion-runtime'
$HostIdlePath = Join-Path $HostIdleDir 'host-idle.json'
$BridgePidPath = Join-Path $HostIdleDir 'host-idle-bridge.pid'
$InstalledBridgePath = 'C:\HermesAgent\bin\Orion-Host-Idle-Bridge.ps1'
$TaskName = 'Orion Host Idle Bridge'

$Stamp = [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$EvidenceRoot = 'E:\Orion-Phase2\P4-02B1A-evidence'
$EvidenceDir = Join-Path $EvidenceRoot ("p4-02b1a-durable-startup-{0}" -f $Stamp)
$BuildDir = Join-Path $EvidenceDir 'build'
$DockerfilePath = Join-Path $BuildDir 'Dockerfile'
$DaemonRunPath = Join-Path $BuildDir 's6\orion-iai-daemon\run'
$BridgeSourcePath = Join-Path $BuildDir 'Orion-Host-Idle-Bridge.ps1'
$TaskInstallerPath = Join-Path $BuildDir 'Install-Orion-Host-Idle-Bridge-Task.ps1'
$SummaryPath = Join-Path $EvidenceDir 'durable-startup-summary.json'
$BackupContainer = "orion-iai-m5-c-pre-durable-$($Stamp.ToLowerInvariant())"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$PreDefaultState = $null
$PreCompanionState = $null
$PreDashboardId = $null
$PreDashboardStartedAt = $null
$PreConfigHash = $null
$PreEnvHash = $null
$PreSoulHash = $null
$PreKeyHash = $null
$PreBrainSize = $null
$MutationStarted = $false
$OldRenamed = $false
$NewCreated = $false

New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $DaemonRunPath) | Out-Null

function Invoke-NativeCapture {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$NativeArgs,
        [AllowNull()][string]$InputText = $null
    )

    $saved = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ($null -eq $InputText) {
            $raw = @(& $FilePath @NativeArgs 2>&1)
        }
        else {
            $raw = @($InputText | & $FilePath @NativeArgs 2>&1)
        }
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $saved
    }

    return [pscustomobject]@{
        ExitCode = [int]$exitCode
        Lines = @($raw | ForEach-Object { [string]$_ })
        Text = (@($raw | ForEach-Object { [string]$_ }) -join [Environment]::NewLine)
    }
}

function Require-NativeSuccess {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)]$Result
    )
    if ($Result.ExitCode -ne 0) {
        throw ("{0} failed with exit {1}: {2}" -f $Label, $Result.ExitCode, $Result.Text)
    }
}

function Invoke-DockerChecked {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [AllowNull()][string]$InputText = $null
    )
    $r = Invoke-NativeCapture -FilePath 'docker.exe' -NativeArgs $Arguments -InputText $InputText
    Require-NativeSuccess -Label $Label -Result $r
    return $r
}

function Get-InspectObject {
    param([Parameter(Mandatory = $true)][string]$Name)
    $r = Invoke-DockerChecked -Label ("inspect {0}" -f $Name) -Arguments @('inspect', $Name)
    $items = @($r.Text | ConvertFrom-Json)
    if ($items.Count -ne 1) {
        throw ("Expected one inspect object for {0}; got {1}" -f $Name, $items.Count)
    }
    return $items[0]
}

function Get-ImageInspectObject {
    param([Parameter(Mandatory = $true)][string]$Image)
    $r = Invoke-DockerChecked -Label ("inspect image {0}" -f $Image) -Arguments @('image','inspect',$Image)
    $items = @($r.Text | ConvertFrom-Json)
    if ($items.Count -ne 1) {
        throw ("Expected one image inspect object for {0}; got {1}" -f $Image, $items.Count)
    }
    return $items[0]
}

function Get-ImageLabel {
    param(
        [Parameter(Mandatory = $true)]$ImageInspect,
        [Parameter(Mandatory = $true)][string]$Name
    )
    if ($null -eq $ImageInspect.Config -or $null -eq $ImageInspect.Config.Labels) {
        return $null
    }
    $p = @($ImageInspect.Config.Labels.PSObject.Properties | Where-Object { $_.Name -eq $Name } | Select-Object -First 1)
    if ($p.Count -eq 0) {
        return $null
    }
    return [string]$p[0].Value
}

function Test-ContainerExists {
    param([Parameter(Mandatory = $true)][string]$Name)
    $r = Invoke-NativeCapture -FilePath 'docker.exe' -NativeArgs @('inspect',$Name)
    return ($r.ExitCode -eq 0)
}

function Get-GatewayState {
    param(
        [Parameter(Mandatory = $true)][string]$Container,
        [Parameter(Mandatory = $true)][string]$Service
    )
    $r = Invoke-DockerChecked -Label ("gateway state {0}" -f $Service) -Arguments @(
        'exec',$Container,'/command/s6-svstat',("/run/service/{0}" -f $Service)
    )
    $text = $r.Text.Trim()
    if ($text -match '^up \(pid (\d+) pgid (\d+)\)') {
        return [pscustomobject]@{ State='up'; ProcId=[int]$Matches[1]; Raw=$text }
    }
    if ($text -match '^down ') {
        return [pscustomobject]@{ State='down'; ProcId=$null; Raw=$text }
    }
    throw ("Unrecognized gateway state for {0}: {1}" -f $Service, $text)
}

function Wait-S6Ready {
    param([Parameter(Mandatory = $true)][string]$Container)
    $probe = @'
from pathlib import Path
ok = Path("/command/s6-svstat").is_file() and Path("/run/service").is_dir()
print("S6_READY=" + ("YES" if ok else "NO"))
raise SystemExit(0 if ok else 2)
'@
    $deadline = (Get-Date).AddSeconds(90)
    $last = ''
    while ((Get-Date) -lt $deadline) {
        $r = Invoke-NativeCapture -FilePath 'docker.exe' -NativeArgs @(
            'exec','-i',$Container,'/usr/bin/python3','-'
        ) -InputText $probe
        $last = $r.Text
        if ($r.ExitCode -eq 0 -and $r.Text -match '(?m)^S6_READY=YES\r?$') {
            return
        }
        Start-Sleep -Milliseconds 500
    }
    throw ("s6 readiness timeout: {0}" -f $last)
}

function Wait-ProfileSlots {
    param([Parameter(Mandatory = $true)][string]$Container)
    $probe = @'
from pathlib import Path
ok = (
    Path("/run/service/gateway-companion").is_dir()
    and Path("/run/service/gateway-default").is_dir()
)
print("PROFILE_SLOTS_READY=" + ("YES" if ok else "NO"))
raise SystemExit(0 if ok else 2)
'@
    $deadline = (Get-Date).AddSeconds(90)
    $last = ''
    while ((Get-Date) -lt $deadline) {
        $r = Invoke-NativeCapture -FilePath 'docker.exe' -NativeArgs @(
            'exec','-i',$Container,'/usr/bin/python3','-'
        ) -InputText $probe
        $last = $r.Text
        if ($r.ExitCode -eq 0 -and $r.Text -match '(?m)^PROFILE_SLOTS_READY=YES\r?$') {
            return
        }
        Start-Sleep -Milliseconds 500
    }
    throw ("profile slot readiness timeout: {0}" -f $last)
}

function Wait-IaiDaemon {
    param([Parameter(Mandatory = $true)][string]$Container)
    $probe = @'
from pathlib import Path
import json
import stat

root = Path("/opt/data/profiles/companion/.iai-mcp")
state_path = root / ".daemon-state.json"
sock = root / ".daemon.sock"

if not state_path.is_file():
    raise SystemExit(2)

state = json.loads(state_path.read_text(encoding="utf-8"))
pid = state.get("daemon_pid")
if not isinstance(pid, int) or pid <= 0:
    raise SystemExit(3)

proc = Path(f"/proc/{pid}")
if not proc.exists() or proc.stat().st_uid != 10000:
    raise SystemExit(4)

if not sock.exists() or not stat.S_ISSOCK(sock.stat().st_mode) or sock.stat().st_uid != 10000:
    raise SystemExit(5)

print("DAEMON_PID=" + str(pid))
print("DAEMON_STATE=" + str(state.get("fsm_state") or state.get("state") or ""))
print("DAEMON_READY=PASS")
'@
    $deadline = (Get-Date).AddSeconds(90)
    $last = ''
    while ((Get-Date) -lt $deadline) {
        $r = Invoke-NativeCapture -FilePath 'docker.exe' -NativeArgs @(
            'exec','-i','-u','10000:10000',
            '-e',("HOME={0}" -f $ProfileRoot),
            '-e',("IAI_MCP_STORE={0}" -f $StoreRoot),
            '-e',("IAI_DAEMON_SOCKET_PATH={0}" -f $SocketPath),
            $Container,$IaiPython,'-'
        ) -InputText $probe
        $last = $r.Text
        if ($r.ExitCode -eq 0 -and $r.Text -match '(?m)^DAEMON_READY=PASS\r?$') {
            return $r
        }
        Start-Sleep -Milliseconds 500
    }
    throw ("iai daemon readiness timeout: {0}" -f $last)
}

function Wait-CompanionReady {
    param([Parameter(Mandatory = $true)][string]$Container)
    $probe = @'
import socket
from pathlib import Path
from iai_mcp.heartbeat_scanner import HeartbeatScanner

store = Path("/opt/data/profiles/companion/.iai-mcp")
api_ok = False
try:
    with socket.create_connection(("127.0.0.1", 8642), timeout=1.0):
        pass
    api_ok = True
except OSError:
    pass

fresh = HeartbeatScanner(store / "wrappers").fresh_count()
print("COMPANION_API_READY=" + ("YES" if api_ok else "NO"))
print("COMPANION_FRESH_WRAPPER_COUNT=" + str(fresh))
raise SystemExit(0 if api_ok and fresh >= 1 else 2)
'@
    $deadline = (Get-Date).AddSeconds(300)
    $last = ''
    while ((Get-Date) -lt $deadline) {
        $r = Invoke-NativeCapture -FilePath 'docker.exe' -NativeArgs @(
            'exec','-i','-u','10000:10000',
            '-e',("HOME={0}" -f $ProfileRoot),
            '-e',("IAI_MCP_STORE={0}" -f $StoreRoot),
            '-e',("IAI_DAEMON_SOCKET_PATH={0}" -f $SocketPath),
            $Container,$IaiPython,'-'
        ) -InputText $probe
        $last = $r.Text
        if ($r.ExitCode -eq 0) {
            return $r
        }
        Start-Sleep -Seconds 2
    }
    throw ("COMPANION readiness timeout: {0}" -f $last)
}

function Verify-ExternalIdle {
    param([Parameter(Mandatory = $true)][string]$Container)
    $probe = @'
from iai_mcp.idle_detector import IdleDetector
idle, source = IdleDetector().os_idle_time_sec()
print("EXTERNAL_IDLE_SOURCE=" + str(source))
print("EXTERNAL_IDLE_SEC=" + str(idle))
raise SystemExit(0 if source == "external_idle_file" and idle is not None and idle >= 0 else 3)
'@
    $r = Invoke-DockerChecked -Label 'verify external idle source' -Arguments @(
        'exec','-i','-u','10000:10000',
        '-e',("HOME={0}" -f $ProfileRoot),
        '-e',("IAI_MCP_STORE={0}" -f $StoreRoot),
        '-e',("IAI_DAEMON_SOCKET_PATH={0}" -f $SocketPath),
        $Container,$IaiPython,'-'
    ) -InputText $probe
    return $r
}

function Set-GatewayToState {
    param(
        [Parameter(Mandatory = $true)][string]$Container,
        [Parameter(Mandatory = $true)][ValidateSet('default','companion')][string]$Profile,
        [Parameter(Mandatory = $true)][ValidateSet('up','down')][string]$State
    )

    $service = "gateway-$Profile"
    $current = Get-GatewayState -Container $Container -Service $service
    if ($current.State -eq $State) {
        return $current
    }

    $gatewayArgs = @('exec',$Container,$HermesCli)
    if ($Profile -eq 'companion') {
        $gatewayArgs += @('-p','companion')
    }
    $gatewayArgs += @('gateway', $(if ($State -eq 'up') { 'start' } else { 'stop' }))
    $null = Invoke-DockerChecked -Label ("set {0} gateway {1}" -f $Profile,$State) -Arguments $gatewayArgs

    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        $current = Get-GatewayState -Container $Container -Service $service
        if ($current.State -eq $State) {
            return $current
        }
        Start-Sleep -Milliseconds 500
    }
    throw ("Gateway {0} did not reach {1}." -f $Profile,$State)
}

function Get-DurableFingerprint {
    param([Parameter(Mandatory = $true)][string]$Container)
    $probe = @'
from pathlib import Path
import hashlib

root = Path("/opt/data/profiles/companion")
store = root / ".iai-mcp"

paths = {
    "CONFIG": root / "config.yaml",
    "ENV": root / ".env",
    "SOUL": root / "SOUL.md",
    "KEY": store / ".crypto.key",
}
for name, path in paths.items():
    if not path.is_file():
        raise SystemExit("missing " + str(path))
    print(name + "=" + hashlib.sha256(path.read_bytes()).hexdigest())

brain = store / "hippo" / "brain.sqlite3"
if not brain.is_file():
    raise SystemExit("missing " + str(brain))
print("BRAIN_BYTES=" + str(brain.stat().st_size))
'@
    $r = Invoke-DockerChecked -Label 'durable fingerprint' -Arguments @(
        'exec','-i','-u','10000:10000',
        '-e',("HOME={0}" -f $ProfileRoot),
        '-e',("IAI_MCP_STORE={0}" -f $StoreRoot),
        $Container,$IaiPython,'-'
    ) -InputText $probe

    $map = @{}
    foreach ($line in $r.Lines) {
        if ([string]$line -match '^([A-Z_]+)=(.+)$') {
            $map[$Matches[1]] = $Matches[2]
        }
    }
    foreach ($key in @('CONFIG','ENV','SOUL','KEY','BRAIN_BYTES')) {
        if (-not $map.ContainsKey($key)) {
            throw ("Fingerprint field missing: {0}" -f $key)
        }
    }
    return $map
}

function Extract-RepoText {
    param(
        [Parameter(Mandatory = $true)][string]$RepoPath,
        [Parameter(Mandatory = $true)][string]$Destination,
        [switch]$UnixLineEndings
    )
    $show = Invoke-NativeCapture -FilePath 'git.exe' -NativeArgs @(
        '-C',$OrionRepo,'show',("{0}:{1}" -f $DurableRef,$RepoPath)
    )
    Require-NativeSuccess -Label ("extract {0}" -f $RepoPath) -Result $show
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null

    $content = $show.Text
    if ($UnixLineEndings) {
        $content = $content -replace "`r`n","`n"
        $content = $content -replace "`r","`n"
        $content += "`n"
    }
    else {
        $content += [Environment]::NewLine
    }

    [System.IO.File]::WriteAllText(
        $Destination,
        $content,
        $Utf8NoBom
    )
}

function Wait-HostBridgeTwoSamples {
    $deadline = (Get-Date).AddSeconds(75)
    $firstSeq = $null
    $firstInstance = $null
    $firstPid = $null
    $last = '<none>'

    while ((Get-Date) -lt $deadline) {
        try {
            if (
                (Test-Path -LiteralPath $BridgePidPath -PathType Leaf) -and
                (Test-Path -LiteralPath $HostIdlePath -PathType Leaf)
            ) {
                $pidRec = (Get-Content -LiteralPath $BridgePidPath -Raw) | ConvertFrom-Json
                $obs = (Get-Content -LiteralPath $HostIdlePath -Raw) | ConvertFrom-Json

                $pidValue = [int]$pidRec.pid
                $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
                if ($null -eq $proc) {
                    throw ("bridge PID {0} is not alive" -f $pidValue)
                }

                $actualStarted = [DateTimeOffset]$proc.StartTime.ToUniversalTime()
                $recordStarted = [DateTimeOffset]::Parse([string]$pidRec.process_started_at)
                $seen = [DateTimeOffset]::Parse([string]$obs.observed_at)
                $age = ([DateTimeOffset]::UtcNow - $seen.ToUniversalTime()).TotalSeconds
                $seq = [int64]$obs.sequence
                $idle = [double]$obs.idle_sec
                $instance = [string]$obs.producer_instance_id
                $valid = (
                    [int]$pidRec.schema_version -eq 1 -and
                    [int]$obs.schema_version -eq 1 -and
                    [string]$obs.source -eq 'windows-get-last-input-info' -and
                    $instance -eq [string]$pidRec.producer_instance_id -and
                    [int]$obs.producer_pid -eq $pidValue -and
                    [math]::Abs(($actualStarted - $recordStarted).TotalSeconds) -le 1.0 -and
                    $age -ge -5.0 -and
                    $age -le 25.0 -and
                    -not [double]::IsNaN($idle) -and
                    -not [double]::IsInfinity($idle) -and
                    $idle -ge 0.0
                )

                if ($valid) {
                    if ($null -eq $firstSeq) {
                        $firstSeq = $seq
                        $firstInstance = $instance
                        $firstPid = $pidValue
                        Write-Host ("P4_02B1A_DURABLE_BRIDGE_SAMPLE1=seq={0}|idle_sec={1}|age={2:N3}" -f `
                            $seq,[int64][math]::Floor($idle),$age)
                    }
                    elseif ($instance -eq $firstInstance -and $pidValue -eq $firstPid -and $seq -gt [int64]$firstSeq) {
                        Write-Host ("P4_02B1A_DURABLE_BRIDGE_SAMPLE2=seq={0}|idle_sec={1}|age={2:N3}" -f `
                            $seq,[int64][math]::Floor($idle),$age)
                        return [pscustomobject]@{
                            Instance=$instance
                            Pid=$pidValue
                            FirstSequence=[int64]$firstSeq
                            Sequence=$seq
                            IdleSec=[int64][math]::Floor($idle)
                        }
                    }
                }

                $last = ("pid={0} instance={1} seq={2} idle={3} age={4}" -f $pidValue,$instance,$seq,$idle,$age)
            }
        }
        catch {
            $last = $_.Exception.Message
        }
        Start-Sleep -Milliseconds 250
    }

    throw ("Scheduled host-idle bridge did not produce two correlated fresh samples: {0}" -f $last)
}

function Verify-TaskDefinition {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    if ([string]$task.Principal.LogonType -notmatch 'Interactive') {
        throw ("Host-idle task is not interactive: {0}" -f $task.Principal.LogonType)
    }
    $triggers = @($task.Triggers)
    if (@($triggers | Where-Object { [string]$_.CimClass.CimClassName -eq 'MSFT_TaskLogonTrigger' }).Count -lt 1) {
        throw 'Host-idle task does not have a logon trigger.'
    }
    if ([string]$task.Settings.MultipleInstances -ne 'IgnoreNew') {
        throw ("Host-idle task MultipleInstances drift: {0}" -f $task.Settings.MultipleInstances)
    }
    if ([int]$task.Settings.RestartCount -ne 10) {
        throw ("Host-idle task RestartCount drift: {0}" -f $task.Settings.RestartCount)
    }
    Write-Host 'P4_02B1A_DURABLE_TASK_DEFINITION=PASS'
}

function Rollback-OldCore {
    if (-not $MutationStarted) {
        return
    }

    Write-Host 'P4_02B1A_DURABLE_ROLLBACK=BEGIN'
    try {
        if ($NewCreated -and (Test-ContainerExists -Name $Core)) {
            $null = Invoke-NativeCapture -FilePath 'docker.exe' -NativeArgs @('rm','-f',$Core)
        }

        if ($OldRenamed -and (Test-ContainerExists -Name $BackupContainer)) {
            $null = Invoke-DockerChecked -Label 'rollback rename old core' -Arguments @('rename',$BackupContainer,$Core)
            $null = Invoke-DockerChecked -Label 'rollback start old core' -Arguments @('start',$Core)
            Wait-S6Ready -Container $Core
            Wait-ProfileSlots -Container $Core

            if ($null -ne $PreDefaultState) {
                $null = Set-GatewayToState -Container $Core -Profile 'default' -State $PreDefaultState.State
            }
            if ($null -ne $PreCompanionState) {
                $null = Set-GatewayToState -Container $Core -Profile 'companion' -State $PreCompanionState.State
            }

            # The old image predates s6 ownership of iai. Restore the daemon only
            # on rollback so the pre-deploy runtime is usable.
            $daemonArgs = @(
                'exec','-d','-u','10000:10000',
                '-e',("HOME={0}" -f $ProfileRoot),
                '-e',("HERMES_HOME={0}" -f $ProfileRoot),
                '-e',("IAI_MCP_STORE={0}" -f $StoreRoot),
                '-e',("IAI_MCP_HERMES_HOME={0}" -f $ProfileRoot),
                '-e',("IAI_DAEMON_SOCKET_PATH={0}" -f $SocketPath),
                '-e',("IAI_MCP_SESSION_RECALL_CLI={0}" -f $IaiCli),
                '-e','HF_HOME=/opt/iai/hf',
                '-e','IAI_MCP_EMBED_OFFLINE=1',
                '-e','PYTHONDONTWRITEBYTECODE=1',
                '-e',("IAI_MCP_EXTERNAL_IDLE_PATH={0}" -f $ExternalIdleContainerPath),
                $Core,$IaiPython,'-m','iai_mcp.daemon'
            )
            $null = Invoke-DockerChecked -Label 'rollback start iai daemon' -Arguments $daemonArgs
            $daemonReady = Wait-IaiDaemon -Container $Core
            Write-Host $daemonReady.Text

            if ($PreCompanionState.State -eq 'up') {
                $ready = Wait-CompanionReady -Container $Core
                Write-Host $ready.Text
            }
        }

        Write-Host 'P4_02B1A_DURABLE_ROLLBACK=PASS'
    }
    catch {
        Write-Host ("P4_02B1A_DURABLE_ROLLBACK_FATAL={0}" -f $_.Exception.Message)
    }
}

Write-Host 'P4-02B1A durable startup deployment'
Write-Host 'Installs native supervision: Docker restart policy + s6 iai daemon + Windows Task Scheduler host-idle bridge.'
Write-Host 'One bounded core recreation is required; persistent memory volume and accepted security/network topology are preserved.'
Write-Host ("P4_02B1A_DURABLE_EVIDENCE={0}" -f $EvidenceDir)

try {
    foreach ($tool in @('docker.exe','git.exe')) {
        if ($null -eq (Get-Command $tool -ErrorAction SilentlyContinue)) {
            throw ("Required tool not found: {0}" -f $tool)
        }
    }
    if (-not (Test-Path -LiteralPath $OrionRepo -PathType Container)) {
        throw ("Orion repository clone missing: {0}" -f $OrionRepo)
    }

    $pre = Get-InspectObject -Name $Core
    if ([string]$pre.Id -ne $ExpectedCoreId -or -not [bool]$pre.State.Running -or [string]$pre.State.StartedAt -ne $ExpectedCoreStartedAt) {
        throw 'Accepted core identity/running state drifted from the verified recovery baseline.'
    }
    if ([string]$pre.Config.Image -ne $BaseImage -or [string]$pre.Image -ne $ExpectedBaseImageId) {
        throw 'Accepted core image drift.'
    }
    if ([string]$pre.HostConfig.RestartPolicy.Name -ne 'no') {
        throw ("Expected pre-durable restart policy no; found {0}" -f $pre.HostConfig.RestartPolicy.Name)
    }
    if (@($pre.Config.Cmd).Count -ne 2 -or [string]$pre.Config.Cmd[0] -ne 'sleep' -or [string]$pre.Config.Cmd[1] -ne 'infinity') {
        throw 'Accepted core command drift.'
    }
    if ([int64]$pre.HostConfig.Memory -ne 0 -or [int64]$pre.HostConfig.NanoCpus -ne 0) {
        throw 'Unexpected resource-limit drift.'
    }

    $mounts = @($pre.Mounts)
    $dataMounts = @($mounts | Where-Object {
        $_.Type -eq 'volume' -and $_.Name -eq $DataVolume -and $_.Destination -eq '/opt/data' -and $_.RW
    })
    $idleMounts = @($mounts | Where-Object {
        $_.Type -eq 'bind' -and $_.Destination -eq '/orion-host-idle' -and -not $_.RW
    })
    if ($dataMounts.Count -ne 1 -or $idleMounts.Count -ne 1 -or $mounts.Count -ne 2) {
        throw 'Accepted core mount topology drift.'
    }

    $networkNames = @($pre.NetworkSettings.Networks.PSObject.Properties.Name | Sort-Object)
    if (($networkNames -join ',') -ne ((@('bridge',$ControlNetwork) | Sort-Object) -join ',')) {
        throw ("Accepted core network topology drift: {0}" -f ($networkNames -join ','))
    }
    if ($null -ne $pre.HostConfig.PortBindings -and @($pre.HostConfig.PortBindings.PSObject.Properties).Count -gt 0) {
        throw 'Accepted core unexpectedly has published ports.'
    }

    $expectedCaps = @('CAP_CHOWN','CAP_DAC_OVERRIDE','CAP_FOWNER','CAP_KILL','CAP_SETGID','CAP_SETUID') | Sort-Object
    $actualCaps = @($pre.HostConfig.CapAdd | ForEach-Object { [string]$_ } | Sort-Object)
    if (($actualCaps -join ',') -ne ($expectedCaps -join ',')) {
        throw ("CapAdd drift: {0}" -f ($actualCaps -join ','))
    }
    $capDrop = @($pre.HostConfig.CapDrop | ForEach-Object { [string]$_ })
    if ($capDrop.Count -ne 1 -or $capDrop[0] -ne 'ALL') {
        throw 'CapDrop drift.'
    }
    $security = @($pre.HostConfig.SecurityOpt | ForEach-Object { [string]$_ })
    if (@($security | Where-Object { $_ -match '^no-new-privileges(?::true)?$' }).Count -ne 1) {
        throw 'no-new-privileges drift.'
    }

    $dash = Get-InspectObject -Name $Dashboard
    if (-not [bool]$dash.State.Running) {
        throw 'Brain dashboard is not running.'
    }
    $PreDashboardId = [string]$dash.Id
    $PreDashboardStartedAt = [string]$dash.State.StartedAt

    $PreDefaultState = Get-GatewayState -Container $Core -Service 'gateway-default'
    $PreCompanionState = Get-GatewayState -Container $Core -Service 'gateway-companion'
    Write-Host ("P4_02B1A_DURABLE_GATEWAY_DEFAULT_PRE={0}" -f $PreDefaultState.State)
    Write-Host ("P4_02B1A_DURABLE_GATEWAY_COMPANION_PRE={0}" -f $PreCompanionState.State)

    $fp = Get-DurableFingerprint -Container $Core
    $PreConfigHash = [string]$fp.CONFIG
    $PreEnvHash = [string]$fp.ENV
    $PreSoulHash = [string]$fp.SOUL
    $PreKeyHash = [string]$fp.KEY
    $PreBrainSize = [int64]$fp.BRAIN_BYTES
    Write-Host 'P4_02B1A_DURABLE_CORE_PREFLIGHT=PASS'

    $fetch = Invoke-NativeCapture -FilePath 'git.exe' -NativeArgs @(
        '-C',$OrionRepo,'fetch','origin',
        '+refs/heads/feature/p4-02b1a-durable-startup:refs/remotes/origin/feature/p4-02b1a-durable-startup'
    )
    Require-NativeSuccess -Label 'fetch durable startup branch' -Result $fetch

    $commit = Invoke-NativeCapture -FilePath 'git.exe' -NativeArgs @('-C',$OrionRepo,'rev-parse',$DurableCommit)
    Require-NativeSuccess -Label 'resolve durable startup implementation commit' -Result $commit
    if ($commit.Text.Trim() -ne $DurableCommit) {
        throw ("Durable startup commit resolution drift: {0}" -f $commit.Text.Trim())
    }

    $ancestor = Invoke-NativeCapture -FilePath 'git.exe' -NativeArgs @(
        '-C',$OrionRepo,'merge-base','--is-ancestor',$DurableCommit,$DurableBranchRef
    )
    if ($ancestor.ExitCode -ne 0) {
        throw 'Pinned durable startup commit is not present on the fetched durable-startup branch.'
    }
    Write-Host ("P4_02B1A_DURABLE_SOURCE_COMMIT={0}" -f $DurableCommit)

    Extract-RepoText -RepoPath $DockerfileRepoPath -Destination $DockerfilePath -UnixLineEndings
    Extract-RepoText -RepoPath $DaemonRunRepoPath -Destination $DaemonRunPath -UnixLineEndings
    Extract-RepoText -RepoPath $BridgeRepoPath -Destination $BridgeSourcePath
    Extract-RepoText -RepoPath $TaskInstallerRepoPath -Destination $TaskInstallerPath
    Write-Host 'P4_02B1A_DURABLE_SOURCE_EXTRACT=PASS'

    $baseImage = Get-ImageInspectObject -Image $BaseImage
    if ([string]$baseImage.Id -ne $ExpectedBaseImageId) {
        throw ("Base image ID drift: {0}" -f $baseImage.Id)
    }

    $build = Invoke-DockerChecked -Label 'build supervised Orion core image' -Arguments @(
        'build','--pull=false','--no-cache','--network','none',
        '-t',$SupervisedImage,
        '-f',$DockerfilePath,
        $BuildDir
    )
    Write-Host 'P4_02B1A_DURABLE_IMAGE_BUILD=PASS'

    $supervisedInspect = Get-ImageInspectObject -Image $SupervisedImage
    if ((Get-ImageLabel -ImageInspect $supervisedInspect -Name 'org.orion.p4.iai-daemon-supervision') -ne 's6-rc') {
        throw 'Supervised image missing s6-rc label.'
    }
    if ((Get-ImageLabel -ImageInspect $supervisedInspect -Name 'org.orion.p4.runtime-recovery') -ne 'durable-startup-v1') {
        throw 'Supervised image missing durable-startup label.'
    }

    $imageProbe = @'
from pathlib import Path

root = Path("/etc/s6-overlay/s6-rc.d/orion-iai-daemon")
ok = (
    (root / "type").read_text(encoding="utf-8").strip() == "longrun"
    and (root / "run").is_file()
    and (root / "dependencies.d" / "base").is_file()
    and Path("/etc/s6-overlay/user-bundles.d/user/contents.d/orion-iai-daemon").is_file()
)
print("SUPERVISED_IMAGE_S6_SERVICE=" + ("PASS" if ok else "FAIL"))
raise SystemExit(0 if ok else 2)
'@
    $probe = Invoke-DockerChecked -Label 'disposable supervised-image probe' -Arguments @(
        'run','--rm','-i','--network','none',
        '--entrypoint','/usr/bin/python3',
        $SupervisedImage,'-'
    ) -InputText $imageProbe
    Write-Host $probe.Text

    Write-Host 'P4_02B1A_DURABLE_HOST_MUTATION=BEGIN'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $TaskInstallerPath -BridgeSourcePath $BridgeSourcePath
    if ($LASTEXITCODE -ne 0) {
        throw ("Host-idle scheduled task installer failed with exit {0}." -f $LASTEXITCODE)
    }

    Verify-TaskDefinition
    $bridge = Wait-HostBridgeTwoSamples
    Write-Host ("P4_02B1A_DURABLE_BRIDGE_PID={0}" -f $bridge.Pid)
    Write-Host ("P4_02B1A_DURABLE_BRIDGE_INSTANCE={0}" -f $bridge.Instance)
    Write-Host ("P4_02B1A_DURABLE_BRIDGE_SEQUENCE={0}->{1}" -f $bridge.FirstSequence,$bridge.Sequence)
    Write-Host 'P4_02B1A_DURABLE_HOST_BRIDGE=PASS'

    Write-Host 'P4_02B1A_DURABLE_PREFLIGHT=PASS'
    Write-Host 'P4_02B1A_DURABLE_MUTATION_BOUNDARY=BEGIN'
    $MutationStarted = $true

    if ($PreDefaultState.State -eq 'up') {
        $null = Set-GatewayToState -Container $Core -Profile 'default' -State 'down'
    }
    if ($PreCompanionState.State -eq 'up') {
        $null = Set-GatewayToState -Container $Core -Profile 'companion' -State 'down'
    }

    $null = Invoke-DockerChecked -Label 'stop pre-durable core' -Arguments @('stop','--time','20',$Core)
    $null = Invoke-DockerChecked -Label 'rename pre-durable rollback core' -Arguments @('rename',$Core,$BackupContainer)
    $OldRenamed = $true
    Write-Host ("P4_02B1A_DURABLE_ROLLBACK_CONTAINER={0}" -f $BackupContainer)

    $hostMount = "type=bind,src=$HostIdleDir,dst=/orion-host-idle,readonly"
    $runArgs = @(
        'run','-d',
        '--name',$Core,
        '--restart','unless-stopped',
        '--network','bridge',
        '--cap-drop','ALL',
        '--cap-add','CHOWN',
        '--cap-add','DAC_OVERRIDE',
        '--cap-add','FOWNER',
        '--cap-add','KILL',
        '--cap-add','SETGID',
        '--cap-add','SETUID',
        '--security-opt','no-new-privileges',
        '-e',("IAI_MCP_EXTERNAL_IDLE_PATH={0}" -f $ExternalIdleContainerPath),
        '--mount',("type=volume,src={0},dst=/opt/data" -f $DataVolume),
        '--mount',$hostMount,
        $SupervisedImage,
        'sleep','infinity'
    )
    $created = Invoke-DockerChecked -Label 'create durable supervised Orion core' -Arguments $runArgs
    $NewCreated = $true
    $newId = $created.Text.Trim()
    if ($newId -notmatch '^[0-9a-f]{64}$') {
        throw ("Unexpected new core ID: {0}" -f $newId)
    }

    $null = Invoke-DockerChecked -Label 'attach durable core to Orion control network' -Arguments @(
        'network','connect',$ControlNetwork,$Core
    )

    Wait-S6Ready -Container $Core
    Wait-ProfileSlots -Container $Core

    $daemonReady = Wait-IaiDaemon -Container $Core
    Write-Host $daemonReady.Text
    Write-Host 'P4_02B1A_DURABLE_S6_DAEMON=PASS'

    $null = Set-GatewayToState -Container $Core -Profile 'default' -State $PreDefaultState.State
    $null = Set-GatewayToState -Container $Core -Profile 'companion' -State $PreCompanionState.State

    if ($PreCompanionState.State -eq 'up') {
        $companionReady = Wait-CompanionReady -Container $Core
        Write-Host $companionReady.Text
    }
    $idleReady = Verify-ExternalIdle -Container $Core
    Write-Host $idleReady.Text

    $post = Get-InspectObject -Name $Core
    if ([string]$post.HostConfig.RestartPolicy.Name -ne 'unless-stopped') {
        throw ("Durable core restart policy mismatch: {0}" -f $post.HostConfig.RestartPolicy.Name)
    }
    if ([string]$post.Config.Image -ne $SupervisedImage) {
        throw ("Durable core image tag mismatch: {0}" -f $post.Config.Image)
    }
    if (@($post.Config.Env | Where-Object { $_ -eq ("IAI_MCP_EXTERNAL_IDLE_PATH={0}" -f $ExternalIdleContainerPath) }).Count -ne 1) {
        throw 'Durable core missing container-level external idle environment.'
    }
    if ($null -ne $post.HostConfig.PortBindings -and @($post.HostConfig.PortBindings.PSObject.Properties).Count -gt 0) {
        throw 'Durable core unexpectedly has published ports.'
    }

    $postFp = Get-DurableFingerprint -Container $Core
    if (
        [string]$postFp.CONFIG -ne $PreConfigHash -or
        [string]$postFp.ENV -ne $PreEnvHash -or
        [string]$postFp.SOUL -ne $PreSoulHash -or
        [string]$postFp.KEY -ne $PreKeyHash -or
        [int64]$postFp.BRAIN_BYTES -ne $PreBrainSize
    ) {
        throw 'Durable state fingerprint changed during supervised-core recreation.'
    }
    Write-Host 'P4_02B1A_DURABLE_STATE_PRESERVED=PASS'

    $dashPost = Get-InspectObject -Name $Dashboard
    if (
        [string]$dashPost.Id -ne $PreDashboardId -or
        [string]$dashPost.State.StartedAt -ne $PreDashboardStartedAt -or
        -not [bool]$dashPost.State.Running
    ) {
        throw 'Brain dashboard changed during durable startup deployment.'
    }
    Write-Host 'P4_02B1A_DURABLE_DASHBOARD_UNCHANGED=PASS'

    # One deliberate container-level restart proves that the iai daemon is now
    # started by s6 rather than by a host-side docker exec.
    $restart = Invoke-DockerChecked -Label 'restart durable core for supervision proof' -Arguments @(
        'restart','--time','20',$Core
    )
    Write-Host 'P4_02B1A_DURABLE_RESTART_TEST=BEGIN'

    Wait-S6Ready -Container $Core
    Wait-ProfileSlots -Container $Core

    $daemonAfterRestart = Wait-IaiDaemon -Container $Core
    Write-Host $daemonAfterRestart.Text
    Write-Host 'P4_02B1A_DURABLE_DAEMON_AUTO_RECOVERY=PASS'

    $restartDefault = Get-GatewayState -Container $Core -Service 'gateway-default'
    $restartCompanion = Get-GatewayState -Container $Core -Service 'gateway-companion'
    if (
        $restartDefault.State -ne $PreDefaultState.State -or
        $restartCompanion.State -ne $PreCompanionState.State
    ) {
        throw ("Gateway state did not auto-recover after container restart: default={0}, companion={1}" -f `
            $restartDefault.State,$restartCompanion.State)
    }
    Write-Host 'P4_02B1A_DURABLE_GATEWAY_AUTO_RECOVERY=PASS'

    if ($PreCompanionState.State -eq 'up') {
        $companionAfterRestart = Wait-CompanionReady -Container $Core
        Write-Host $companionAfterRestart.Text
    }
    $idleAfterRestart = Verify-ExternalIdle -Container $Core
    Write-Host $idleAfterRestart.Text

    $final = Get-InspectObject -Name $Core
    if ([string]$final.Id -ne $newId) {
        throw 'Container ID changed during deliberate restart; expected restart, not recreation.'
    }
    if ([string]$final.HostConfig.RestartPolicy.Name -ne 'unless-stopped') {
        throw 'Restart policy lost after deliberate restart.'
    }

    $finalFp = Get-DurableFingerprint -Container $Core
    if (
        [string]$finalFp.CONFIG -ne $PreConfigHash -or
        [string]$finalFp.ENV -ne $PreEnvHash -or
        [string]$finalFp.SOUL -ne $PreSoulHash -or
        [string]$finalFp.KEY -ne $PreKeyHash -or
        [int64]$finalFp.BRAIN_BYTES -ne $PreBrainSize
    ) {
        throw 'Durable state fingerprint changed during deliberate restart.'
    }

    $summary = [ordered]@{
        schema_version = 1
        status = 'PASS'
        deployed_at = [DateTimeOffset]::UtcNow.ToString('o')
        source_commit = $DurableCommit
        base_image = $BaseImage
        base_image_id = $ExpectedBaseImageId
        supervised_image = $SupervisedImage
        supervised_image_id = [string](Get-ImageInspectObject -Image $SupervisedImage).Id
        core_id = [string]$final.Id
        core_started_at = [string]$final.State.StartedAt
        restart_policy = [string]$final.HostConfig.RestartPolicy.Name
        rollback_container = $BackupContainer
        host_idle_task = $TaskName
        host_idle_bridge_pid = $bridge.Pid
        host_idle_bridge_instance = $bridge.Instance
        iai_daemon_supervisor = 's6-rc'
        container_restart_proof = $true
        docker_desktop_restart_proof = $false
        threshold_changes = 'NONE'
        memory_state_edits = 'NONE'
        lifecycle_state_edits = 'NONE'
        dashboard_changed = $false
    }
    [System.IO.File]::WriteAllText(
        $SummaryPath,
        ($summary | ConvertTo-Json -Depth 7),
        $Utf8NoBom
    )

    Write-Host ("P4_02B1A_DURABLE_NEW_CORE_ID={0}" -f $final.Id)
    Write-Host ("P4_02B1A_DURABLE_NEW_CORE_STARTED_AT={0}" -f $final.State.StartedAt)
    Write-Host ("P4_02B1A_DURABLE_SUPERVISED_IMAGE_ID={0}" -f $summary.supervised_image_id)
    Write-Host ("P4_02B1A_DURABLE_SUMMARY={0}" -f $SummaryPath)
    Write-Host 'P4_02B1A_DURABLE_RESTART_POLICY=unless-stopped'
    Write-Host 'P4_02B1A_DURABLE_CONTAINER_RESTART_RECOVERY=PASS'
    Write-Host 'P4_02B1A_DURABLE_THRESHOLDS=UNCHANGED'
    Write-Host 'P4_02B1A_DURABLE_STARTUP=PASS'
    exit 0
}
catch {
    Write-Host ("P4_02B1A_DURABLE_FATAL={0}" -f $_.Exception.Message)
    Rollback-OldCore

    $failure = [ordered]@{
        schema_version = 1
        status = 'FAIL'
        failed_at = [DateTimeOffset]::UtcNow.ToString('o')
        error = $_.Exception.Message
        mutation_started = $MutationStarted
        rollback_container = $(if ($OldRenamed) { $BackupContainer } else { $null })
        threshold_changes = 'NONE'
        memory_state_edits = 'NONE'
        lifecycle_state_edits = 'NONE'
    }
    try {
        [System.IO.File]::WriteAllText(
            $SummaryPath,
            ($failure | ConvertTo-Json -Depth 6),
            $Utf8NoBom
        )
    }
    catch {
    }

    Write-Host ("P4_02B1A_DURABLE_SUMMARY={0}" -f $SummaryPath)
    Write-Host 'P4_02B1A_DURABLE_STARTUP=FAIL'
    exit 1
}
