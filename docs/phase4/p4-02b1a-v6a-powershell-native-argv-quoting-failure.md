# P4-02B1A v6A — PowerShell 5.1 native argv quoting failure

Date: 2026-08-27

## Boundary

The read-only autonomous lifecycle preflight reached runtime preflight and verified the accepted core and Brain dashboard container identities, then failed before the Python probe executed successfully.

No Brain control action was sent. No iai state was edited. No lifecycle thresholds were changed. No container was restarted or recreated.

## Observed failure

The v6A script passed the multiline Python probe to `docker.exe exec ... python -c <script>` as a native command-line argument under Windows PowerShell 5.1. Embedded double quotes in the multiline source were not preserved. The Python source line intended as:

`root = Path(root_env) if root_env else Path.home() / ".iai-mcp"`

arrived in the container as:

`root = Path(root_env) if root_env else Path.home() / .iai-mcp`

and Python exited with `SyntaxError: invalid syntax`.

## Diagnosis

This is a harness transport defect at the Windows PowerShell 5.1 -> native `docker.exe` argument boundary, not an iai lifecycle defect and not a Python logic defect.

The earlier docker-inspect scalar-string indexing defect did not recur; `Get-ContainerState` used the already-joined text safely.

## Correction

Do not pass multiline Python source through `-c` as a native argv element. Pipe the Python source to stdin and run `docker exec -i <container> /opt/iai/venv/bin/python -`. This avoids PowerShell 5.1 embedded-quote reconstruction and command-line-length pressure.

The corrected continuation must remain read-only and preserve the existing acceptance boundary: no controls, no iai state edits, no threshold changes, and no container restart/recreation.
