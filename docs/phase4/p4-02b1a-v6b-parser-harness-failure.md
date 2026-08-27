# P4-02B1A v6B — Parser Harness Failure

Date: 2026-08-27 UTC

Status: **HARNESS-ONLY FAILURE / NO RUNTIME ACTION**

The first production autonomous lifecycle observer (`v6B`) failed at PowerShell parse time before any statement executed.

Root cause: a double-quoted error string contained `$Name:`. Windows PowerShell parses the colon as part of a scope/drive-qualified variable reference, so the script failed with `InvalidVariableReferenceWithDrive` before reaching `P4_02B1A_V6B_TOOLS=PASS`.

Faulting form:

```powershell
throw "Unexpected docker inspect output for $Name: $line"
```

Correct form:

```powershell
throw "Unexpected docker inspect output for ${Name}: $line"
```

Because this was a parse-time failure, no Docker inspection, Python probe, Brain control, iai state read/write, threshold change, container restart, or lifecycle observation occurred in this attempt. The accepted production runtime was not touched.

The corrected `v6Br1` observer keeps the same read-only lifecycle-observation scope and adds static generation-time lint checks for suspicious `$word:` interpolation inside double-quoted strings and for raw multiline Python passed through native `python -c` argv transport. The corrected artifact must still pass the Windows PowerShell parser before execution.
