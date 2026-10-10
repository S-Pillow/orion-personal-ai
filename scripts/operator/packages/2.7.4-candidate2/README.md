# Orion operator 2.7.4-candidate2

Status: source candidate for P0 lifecycle provenance compatibility. Not installed or deployed by Stage B.

This package is reconstructed from the installed accepted `2.7.4-candidate1`
runtime engine after exact hash verification. The original four-line
`Stop-Orion.ps1` wrapper is recovered from the preserved
`Stop-Orion.ps1.drift-20260912-030931` artifact, not from the later in-place legacy Stop
replacement.

Candidate2 changes only:

1. `protocol.py` version becomes `2.7.4-candidate2`.
2. Start/Stop wrappers resolve `orion-config.json` inside the script body and
   continue routing through `Invoke-Orion.ps1` / `orion.py`.
3. `orion.py` replaces the obsolete empty-worktree requirement with
   `hermes_provenance.verify_hermes_provenance()`.
4. `hermes_provenance.py` fail-closes on the exact accepted Hermes pin,
   porcelain status/path set, SHA-256 values, and P4/P5 semantic sidecar
   identities.

`orion-config.json` is deliberately not source-controlled here because the
accepted publication config is machine-specific. Publication must copy the
already verified installed config unchanged after its accepted SHA-256 is
reconfirmed.

No Hermes source change, dependency update, reminder behavior, vault authority,
or persistent lifecycle authority is introduced.
