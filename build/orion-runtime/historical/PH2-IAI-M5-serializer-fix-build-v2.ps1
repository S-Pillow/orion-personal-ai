param(
    [Parameter(Mandatory=$true)]
    [string]$EvidenceDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ContainerB = 'orion-iai-m5-b'
$BaseTag = 'orion-hermes-iai:v2026.8.18-iai3.0.8-m4'
$ExpectedBaseImageId = 'sha256:700eb55102b1fadad3c111968794d5b82f581b0ddb616aa028421cb63b721513'
$FixedTag = 'orion-hermes-iai:v2026.8.18-iai3.0.8-m5-serializerfix'
$Marker = 'topaz-6842'
$BuildStateFile = 'E:\Orion-Phase2\PH2-IAI-M5-serializer-fix.json'

New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$ContextDir = Join-Path $EvidenceDir 'serializer-overlay-context'
New-Item -ItemType Directory -Force -Path $ContextDir | Out-Null

function Invoke-DockerRaw {
    param(
        [Parameter(Mandatory=$true)][string[]]$Arguments,
        [AllowNull()][string]$InputText = $null
    )

    $savedPreference = $ErrorActionPreference
    $raw = @()
    $rc = -999

    try {
        $ErrorActionPreference = 'Continue'
        if ($null -eq $InputText) {
            $raw = & docker.exe @Arguments 2>&1
        } else {
            $raw = $InputText | & docker.exe @Arguments 2>&1
        }
        $rc = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedPreference
    }

    return [pscustomobject]@{
        ExitCode = [int]$rc
        Text = (($raw | ForEach-Object { "$_" }) -join "`n")
        Lines = @($raw | ForEach-Object { "$_" })
    }
}

function Invoke-Docker {
    param(
        [Parameter(Mandatory=$true)][string]$Label,
        [Parameter(Mandatory=$true)][string[]]$Arguments
    )

    Write-Host "=== $Label ==="
    $r = Invoke-DockerRaw -Arguments $Arguments
    Write-Host ("exit=" + $r.ExitCode)
    if ($r.Lines.Count -gt 0) {
        $r.Lines | ForEach-Object { Write-Host $_ }
    } else {
        Write-Host '<no output>'
    }
    if ($r.ExitCode -ne 0) {
        throw "$Label failed with exit $($r.ExitCode)"
    }
    return $r
}

function Invoke-DockerStdin {
    param(
        [Parameter(Mandatory=$true)][string]$Label,
        [Parameter(Mandatory=$true)][string[]]$Arguments,
        [Parameter(Mandatory=$true)][string]$InputText
    )

    Write-Host "=== $Label ==="
    $r = Invoke-DockerRaw -Arguments $Arguments -InputText $InputText
    Write-Host ("exit=" + $r.ExitCode)
    if ($r.Lines.Count -gt 0) {
        $r.Lines | ForEach-Object { Write-Host $_ }
    } else {
        Write-Host '<no output>'
    }
    if ($r.ExitCode -ne 0) {
        throw "$Label failed with exit $($r.ExitCode)"
    }
    return $r
}

try {
    Write-Host 'PH2_IAI_M5_SERIALIZER_FIX_BUILD_START=YES'
    Write-Host "EVIDENCE_DIR=$EvidenceDir"
    Write-Host 'SCOPE=BUILD_AND_VERIFY_BOUNDED_IAI_3_0_8_SESSION_START_SERIALIZER_OVERLAY'
    Write-Host 'CONTAINER_B_MUTATION=NONE'
    Write-Host 'M5_DATA_VOLUME_MUTATION=NONE'
    Write-Host 'GATEWAY_MUTATION=NONE'
    Write-Host 'DAEMON_MUTATION=NONE'
    Write-Host 'MODEL_CALLS=NONE'
    Write-Host "M5_MARKER=$Marker"

    $base = Invoke-Docker -Label 'verify accepted M4 combined image identity' -Arguments @(
        'image','inspect',$BaseTag,'--format','{{.Id}}'
    )
    if ($base.Text.Trim() -ne $ExpectedBaseImageId) {
        throw "Accepted base image identity drift: $($base.Text.Trim())"
    }
    Write-Host 'M5_SERIALIZER_FIX_BASE_IMAGE=PASS'

    $b = Invoke-Docker -Label 'verify existing container B remains on accepted unpatched image' -Arguments @(
        'inspect',$ContainerB,'--format','{{.State.Running}}|{{.Image}}|{{json .Config.Cmd}}'
    )
    $bp = $b.Text.Trim().Split('|',3)
    if ($bp.Count -ne 3) { throw 'Unexpected container B inspect shape' }
    if ($bp[0] -ne 'true') { throw 'Container B is not running' }
    if ($bp[1] -ne $ExpectedBaseImageId) { throw "Container B image drift: $($bp[1])" }
    if ($bp[2] -ne '["sleep","infinity"]') { throw "Container B command drift: $($bp[2])" }
    Write-Host 'M5_CONTAINER_B_UNPATCHED_BASE_IDENTITY=PASS'

    $gateway = Invoke-Docker -Label 'verify container B COMPANION gateway remains down before image build' -Arguments @(
        'exec',$ContainerB,'/command/s6-svstat','/run/service/gateway-companion'
    )
    if ($gateway.Text -notmatch '^down ') {
        throw 'Container B COMPANION gateway is not down'
    }
    Write-Host 'M5_CONTAINER_B_GATEWAY_DOWN=PASS'

    $stdinProbeCode = @'
print("DOCKER_RUN_STDIN_BOUNDARY=PASS")
'@

    $stdinProbe = Invoke-DockerStdin `
        -Label 'verify docker run stdin is attached before serializer tests' `
        -Arguments @(
            'run','--rm','-i','--network','none',
            '--entrypoint','/opt/iai/venv/bin/python',
            $BaseTag,'-'
        ) `
        -InputText $stdinProbeCode

    if ($stdinProbe.Text -notmatch '(?m)^DOCKER_RUN_STDIN_BOUNDARY=PASS\r?$') {
        throw 'docker run stdin boundary did not execute the supplied Python'
    }
    Write-Host 'M5_DOCKER_RUN_STDIN_BOUNDARY=PASS'

    $baselineProbe = @'
from pathlib import Path
import importlib.util
import inspect

spec=importlib.util.find_spec("iai_mcp.core._serializers")
if spec is None or not spec.origin:
    print("SERIALIZER_MODULE_FOUND=NO")
    raise SystemExit(2)

path=Path(spec.origin)
text=path.read_text(encoding="utf-8")

from iai_mcp.session import SessionStartPayload
from iai_mcp.core._serializers import _payload_to_json

payload=SessionStartPayload(wake_depth="standard",recent_thread="topaz-6842")
out=_payload_to_json(payload)

print("SERIALIZER_MODULE_FOUND=YES")
print("BASE_SERIALIZER_RECENT_THREAD_KEY="+("YES" if "recent_thread" in out else "NO"))
print("BASE_SERIALIZER_SOURCE_HAS_RECENT_THREAD="+("YES" if '"recent_thread"' in inspect.getsource(_payload_to_json) else "NO"))

if "recent_thread" in out:
    raise SystemExit(3)
if '"recent_thread"' in inspect.getsource(_payload_to_json):
    raise SystemExit(4)

print("BASE_SERIALIZER_OMISSION_REPRODUCED=PASS")
'@

    $baseline = Invoke-DockerStdin `
        -Label 'reproduce exact serializer omission in accepted base image' `
        -Arguments @(
            'run','--rm','-i','--network','none',
            '--entrypoint','/opt/iai/venv/bin/python',
            $BaseTag,'-'
        ) `
        -InputText $baselineProbe

    if ($baseline.Text -notmatch '(?m)^BASE_SERIALIZER_OMISSION_REPRODUCED=PASS\r?$') {
        throw 'Accepted base image did not reproduce the expected serializer omission'
    }
    Write-Host 'M5_SERIALIZER_OMISSION_BASELINE=PASS'

    $overlayPy = @'
from pathlib import Path
import hashlib
import importlib.util
import py_compile

spec=importlib.util.find_spec("iai_mcp.core._serializers")
if spec is None or not spec.origin:
    raise SystemExit("serializer module not found")

path=Path(spec.origin)
text=path.read_text(encoding="utf-8")

old='        "wake_depth": getattr(payload, "wake_depth", "minimal"),\n    }\n'
new=(
    '        "wake_depth": getattr(payload, "wake_depth", "minimal"),\n'
    '        "recent_thread": getattr(payload, "recent_thread", ""),\n'
    '    }\n'
)

if '"recent_thread": getattr(payload, "recent_thread", "")' in text:
    raise SystemExit("serializer already contains recent_thread; refusing non-baseline overlay")
if text.count(old) != 1:
    raise SystemExit(f"expected exactly one serializer anchor, found {text.count(old)}")

before=hashlib.sha256(text.encode("utf-8")).hexdigest()
patched=text.replace(old,new,1)
path.write_text(patched,encoding="utf-8")
py_compile.compile(str(path),doraise=True)
after=hashlib.sha256(path.read_bytes()).hexdigest()

print("OVERLAY_TARGET="+str(path))
print("OVERLAY_BEFORE_SHA256="+before)
print("OVERLAY_AFTER_SHA256="+after)
print("OVERLAY_RECENT_THREAD_SERIALIZER=PASS")
'@

    $dockerfile = @'
FROM orion-hermes-iai:v2026.8.18-iai3.0.8-m4
COPY apply_serializer_overlay.py /tmp/apply_serializer_overlay.py
RUN /opt/iai/venv/bin/python /tmp/apply_serializer_overlay.py
RUN /bin/rm /tmp/apply_serializer_overlay.py
'@

    $overlayPath = Join-Path $ContextDir 'apply_serializer_overlay.py'
    $dockerfilePath = Join-Path $ContextDir 'Dockerfile'
    Set-Content -LiteralPath $overlayPath -Value $overlayPy -Encoding UTF8
    Set-Content -LiteralPath $dockerfilePath -Value $dockerfile -Encoding ASCII

    Write-Host 'M5_SERIALIZER_FIX_BUILD_CONTEXT=READY'

    $existing = Invoke-DockerRaw -Arguments @('image','inspect',$FixedTag,'--format','{{.Id}}')
    if ($existing.ExitCode -eq 0) {
        throw "Fixed image tag already exists ($($existing.Text.Trim())); refusing to overwrite evidence tag"
    }

    Invoke-Docker -Label 'build bounded iai 3.0.8 serializer-fix child image' -Arguments @(
        'build','--pull=false','--no-cache',
        '-t',$FixedTag,
        $ContextDir
    ) | Out-Null

    $fixed = Invoke-Docker -Label 'resolve serializer-fix image identity' -Arguments @(
        'image','inspect',$FixedTag,'--format','{{.Id}}'
    )
    $fixedImageId = $fixed.Text.Trim()
    if ($fixedImageId -notmatch '^sha256:[0-9a-f]{64}$') {
        throw "Unexpected fixed image id: $fixedImageId"
    }
    if ($fixedImageId -eq $ExpectedBaseImageId) {
        throw 'Serializer-fix image id did not change from accepted base image'
    }
    Write-Host "M5_SERIALIZER_FIX_IMAGE_ID=$fixedImageId"
    Write-Host 'M5_SERIALIZER_FIX_IMAGE_ID_CHANGED=PASS'

    $verifyProbe = @'
import inspect
from iai_mcp.session import SessionStartPayload
from iai_mcp.core._serializers import _payload_to_json

payload=SessionStartPayload(
    wake_depth="standard",
    recent_thread="topaz-6842",
)
out=_payload_to_json(payload)
value=out.get("recent_thread")

print("FIXED_SERIALIZER_KEY_PRESENT="+("YES" if "recent_thread" in out else "NO"))
print("FIXED_SERIALIZER_VALUE="+str(value))
print("FIXED_SERIALIZER_SOURCE_HAS_RECENT_THREAD="+("YES" if '"recent_thread"' in inspect.getsource(_payload_to_json) else "NO"))

if value != "topaz-6842":
    raise SystemExit(2)
if '"recent_thread"' not in inspect.getsource(_payload_to_json):
    raise SystemExit(3)

print("FIXED_SERIALIZER_CONTRACT=PASS")
'@

    $verify = Invoke-DockerStdin `
        -Label 'verify recent_thread survives production serializer in fixed image' `
        -Arguments @(
            'run','--rm','-i','--network','none',
            '--entrypoint','/opt/iai/venv/bin/python',
            $FixedTag,'-'
        ) `
        -InputText $verifyProbe

    if ($verify.Text -notmatch '(?m)^FIXED_SERIALIZER_CONTRACT=PASS\r?$') {
        throw 'Serializer-fix image failed isolated serializer contract verification'
    }

    $buildState = [ordered]@{
        base_tag = $BaseTag
        base_image_id = $ExpectedBaseImageId
        fixed_tag = $FixedTag
        fixed_image_id = $fixedImageId
        issue = 'iai-pme 3.0.8 _payload_to_json omits SessionStartPayload.recent_thread'
        overlay = 'add recent_thread field to core._serializers._payload_to_json'
        built_utc = (Get-Date).ToUniversalTime().ToString('o')
        container_b_mutated = $false
        m5_data_volume_mutated = $false
    }
    $buildState | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $BuildStateFile -Encoding UTF8

    Write-Host "M5_SERIALIZER_FIX_STATE_FILE=$BuildStateFile"
    Write-Host 'PH2_IAI_M5_SERIALIZER_FIX_BUILD=PASS'
    Write-Host 'CONTAINER_B_MUTATION=NONE'
    Write-Host 'M5_DATA_VOLUME_MUTATION=NONE'
    Write-Host 'GATEWAY_MUTATION=NONE'
    Write-Host 'DAEMON_MUTATION=NONE'
    Write-Host 'MODEL_CALLS=NONE'
    Write-Host 'NEXT_UNIT=M5_RECREATE_EXISTING_B_ON_SERIALIZER_FIX_IMAGE'
}
catch {
    Write-Host 'PH2_IAI_M5_SERIALIZER_FIX_BUILD=FAIL'
    Write-Host ("FATAL=" + $_.Exception.Message)
    Write-Host 'CONTAINER_B_MUTATION=NONE'
    Write-Host 'M5_DATA_VOLUME_MUTATION=NONE'
    Write-Host 'GATEWAY_MUTATION=NONE'
    Write-Host 'DAEMON_MUTATION=NONE'
    exit 1
}

Write-Host 'PH2_IAI_M5_SERIALIZER_FIX_BUILD_END=PASS'
exit 0
