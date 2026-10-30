# PowerShell Harness Standard for Orion

Status: repository operating standard for AI-authored/operator-run PowerShell harnesses.

## Purpose

Orion frequently uses PowerShell harnesses to qualify source state, run disposable tests, perform controlled lifecycle operations, and execute narrow migrations on Windows. Because those harnesses may sit directly in front of production/runtime mutation, harness correctness is part of the safety boundary.

The recurring failure class this standard is intended to eliminate is not business logic; it is PowerShell's scalar/null/array behavior around native commands, combined with `Set-StrictMode` and optimistic assumptions about command output.

## Mandatory design rules

### 1. Normalize native command output deliberately

PowerShell may return `$null`, a scalar string, or an array depending on how many lines a native command emits. Never write code whose correctness changes across those three shapes.

Use:

```powershell
$Lines = @(& git -C $Repo status --porcelain=v1)
if ($Lines.Count -ne 0) {
    # ...
}
```

Do not use:

```powershell
if ((& git -C $Repo status --porcelain=v1).Count -ne 0) {
    # unsafe when command emits no lines
}
```

The zero-result, one-result, and multi-result cases must all be considered explicitly.

### 2. Never trim unguarded native output

A native command that emits nothing can become `$null` under PowerShell. Under `Set-StrictMode`, calling `.Trim()` on that value aborts the harness.

Preferred pattern:

```powershell
$Raw = @(& git -C $Repo branch --show-current)
$Branch = if ($LASTEXITCODE -eq 0 -and $Raw.Count -gt 0) {
    ([string]$Raw[0]).Trim()
} else {
    ""
}
```

If a single-line result is required, validate the count instead of assuming it.

### 2a. Treat machine-readable native output as a protocol

Do not normalize away whitespace merely because the data came from a command-line program. Some native formats use leading spaces or fixed columns as part of their grammar.

`git status --porcelain=v1` is a concrete Orion example:

```text
 M agent/monitoring/cron_health.py
?? cron/error_classification.py
```

The leading space in the first record is meaningful. Generic `.Trim()`, Python `.strip()`, or equivalent normalization can turn that record into `M agent/...` and corrupt fixed-offset parsing.

Rules:

- only remove the exact record terminator (`CR`, `LF`, or `CRLF`) when the protocol permits it;
- preserve leading and trailing spaces until the format-specific parser has consumed them;
- prefer the producer's documented machine-readable mode (`--porcelain`, `--format`, JSON, etc.);
- validate record length/shape before fixed-position slicing;
- include at least one test/fixture whose first record begins with protocol-significant whitespace.

This rule applies even when a Python helper or another language is used underneath a PowerShell harness. The safety boundary is the whole operator toolchain, not only the `.ps1` file.

### 3. Check native-command exit status immediately

For `git`, `python`, `uv`, service-control utilities, and other native programs, capture or validate `$LASTEXITCODE` immediately after the command whose result matters. Do not allow another native command to overwrite it first.

A command producing plausible text is not proof of success.

### 4. StrictMode is required, but the harness must be written for it

Qualification and migration harnesses should normally start with:

```powershell
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
```

StrictMode is not a substitute for input-shape handling. The script must be intentionally safe under StrictMode for empty values, absent properties, and command-output cardinality.

### 5. Mutation comes after identity and state validation

Whenever practical, order the harness as:

1. required-path checks;
2. exact source/commit identity checks;
3. expected dirty/clean state checks;
4. runtime ownership/state checks;
5. backup/rollback preparation;
6. mutation;
7. post-mutation verification.

A harness bug or stale assumption should fail before mutation.

### 6. Use exact targeting, not broad cleanup

Prefer:

- exact PIDs over `Stop-Process -Name python`;
- exact ports plus process ownership over broad kills;
- exact files over wildcard removal;
- exact commits/tags over floating branches for qualification;
- bounded waits over indefinite polling.

Do not broad-kill Python, Hermes, Ollama, or related processes unless the operation explicitly requires and authorizes it.

### 7. Preserve ownership semantics

Orion lifecycle ownership rules remain authoritative. A harness must not stop, restart, or adopt external/pre-existing services merely because they are present.

Where Orion has accepted lifecycle scripts, use those rather than recreating lifecycle behavior ad hoc.

### 8. Do not print secrets as evidence

Prove presence, shape, source, or successful authenticated behavior without echoing API keys, tokens, passwords, private configuration values, or sensitive file contents.

### 9. Backups and rollback are part of the mutation

For any destructive, source-owning, environment-owning, schema, or dependency mutation, define and verify rollback evidence before performing the change. A backup path should be explicit and should cover the actual state needed to restore service, not merely a convenient subset.

### 10. Disposable means disposable

Candidate source trees, qualification environments, test databases, and generated patches should live outside the accepted installation/runtime paths unless the task explicitly authorizes otherwise. They must not silently become production dependencies.

## Harness qualification checklist

Before giving an operator a PowerShell harness, the author/agent must review at least these cases:

- native command emits zero lines;
- native command emits one line;
- native command emits multiple lines;
- native command exits nonzero with or without output;
- machine-readable output begins with meaningful whitespace;
- expected file/property is absent;
- expected branch is detached or empty;
- expected port/process is already occupied;
- rerun after a partial previous attempt;
- cleanup path when the script aborts before completion;
- whether any preflight step itself mutates state.

For migration/deployment harnesses, also verify:

- exact source identity is pinned;
- dirty-state expectations are explicit;
- backups exist before mutation;
- rollback command/path is known;
- runtime health checks are bounded;
- no unrelated service or profile is changed;
- secret values are not printed;
- post-state is independently re-read rather than inferred from a successful command.

## Recommended helper patterns

### Native output as an array

```powershell
function Invoke-NativeLines {
    param(
        [Parameter(Mandatory)]
        [scriptblock]$Command,
        [Parameter(Mandatory)]
        [string]$Label
    )

    $Lines = @(& $Command)
    $ExitCode = $LASTEXITCODE

    if ($ExitCode -ne 0) {
        throw "$Label failed with exit code $ExitCode."
    }

    return ,$Lines
}
```

The leading comma on return is deliberate when preserving an array value as one return object is required; use simpler direct `@(...)` capture when that is clearer.

### Required single line

```powershell
$Lines = @(& git -C $Repo rev-parse HEAD)
$ExitCode = $LASTEXITCODE

if ($ExitCode -ne 0 -or $Lines.Count -ne 1) {
    throw "Could not resolve exactly one repository HEAD."
}

$Head = ([string]$Lines[0]).Trim()
```

Use this only for a protocol where surrounding whitespace is not meaningful, such as `git rev-parse HEAD`. Do not reuse it for fixed-column records such as `git status --porcelain`.

### Optional single line

```powershell
$Lines = @(& git -C $Repo branch --show-current)
$ExitCode = $LASTEXITCODE

$Branch = if ($ExitCode -eq 0 -and $Lines.Count -gt 0) {
    ([string]$Lines[0]).Trim()
} else {
    ""
}
```

### Bounded polling

```powershell
function Wait-Until {
    param(
        [Parameter(Mandatory)] [scriptblock]$Condition,
        [Parameter(Mandatory)] [int]$Seconds,
        [Parameter(Mandatory)] [string]$FailureMessage
    )

    $Deadline = (Get-Date).AddSeconds($Seconds)
    do {
        if (& $Condition) { return }
        Start-Sleep -Milliseconds 300
    } while ((Get-Date) -lt $Deadline)

    throw $FailureMessage
}
```

## Review standard for AI agents

When a future agent encounters a PowerShell harness bug, it should not merely patch the failing line. It should search the whole harness for the same failure class before returning a corrected version.

For example, after a null/array cardinality failure, review every occurrence of:

- `.Count` on command expressions;
- `.Trim()` on native-command output;
- generic `.strip()`/whitespace normalization in helper languages that parse native output;
- direct `[0]` indexing;
- fixed-position parsing of machine-readable command output;
- `Select-String` result assumptions;
- JSON property access under StrictMode;
- `$LASTEXITCODE` read after another native invocation;
- native command output assigned without `@(...)` where cardinality matters.

A corrected harness should state whether the prior failure occurred before or after mutation and should verify that installed/runtime state remained unchanged rather than assuming it.

## Orion-specific continuity

Future sessions should not rely on chat memory for current source/runtime state. Read `AGENTS.md`, the active task docs, open PRs/issues, and exact commit evidence first. For Hermes migration work, the five hard production gates are Orion, Memory, Voice, Chat, and Security; other subsystem defects matter when their blast radius crosses one of those gates.
