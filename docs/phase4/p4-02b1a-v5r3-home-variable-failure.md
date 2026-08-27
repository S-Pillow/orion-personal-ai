# P4-02B1A v5r3 manual-control harness failure

Status: harness failure before mutating Brain controls

## Observed run

The v5r3 repair wrapper successfully:

- found exactly one docker-inspect scalar-string indexing defect in the original v5 script;
- verified the existing lifecycle reader anchor;
- wrote the repaired v5r3 smoke script;
- passed the Windows PowerShell parser gate;
- launched the repaired manual Brain control smoke;
- verified docker.exe was available;
- read the accepted core container ID and StartedAt;
- read the Brain dashboard container ID.

Execution then stopped with:

```text
Cannot overwrite variable HOME because it is read-only or constant.
```

## Root cause

The original v5 `Resolve-LifecyclePath` helper assigns a local variable named `$home`:

```powershell
$home = Get-ContainerEnvValue -Name $DashboardContainer -Key "HOME"
```

PowerShell variable names are case-insensitive, so `$home` resolves to the automatic/read-only `$HOME` variable. The assignment therefore fails before lifecycle preflight completes.

## Safety boundary

The failure occurred before `P4_02B1A_V5_PREFLIGHT=PASS` and before the first `Invoke-BrainAction` call. No `sleep`, `wake`, `consolidate`, `restart`, or `stop` Brain control request was sent by this attempt.

The commands executed before failure were read-only inspection/GET operations. No source deploy, dashboard restart, accepted core restart/recreation, Docker socket exposure, lifecycle-file edit, or iai memory-semantics change occurred.

## Next bounded correction

Continue from the original v5 source with two narrowly scoped harness corrections only:

1. retain the null-safe array wrapping for `docker inspect` output;
2. rename the local `$home` variable in `Resolve-LifecyclePath` to a non-automatic name such as `$containerHome`.

Do not broaden the patch or change the Brain control acceptance sequence.
