# OR-LIFE-005 Post-Reboot Performance Incident Snapshot — 2026-09-08

Status: **BLOCKED / ROOT CAUSE PENDING**

## Context

After a successful post-reboot manual-off verification, the operator invoked Start Orion from the desktop. The machine then became severely sluggish: PowerShell prompt responsiveness degraded, pasted text took more than 30 seconds to appear, and Task Manager took a long time to open.

## Observed inconsistent runtime state

After the problematic start attempt:

- Hermes API on `127.0.0.1:8642`: **True**
- Ollama API on `127.0.0.1:11434`: **False**
- Orion launcher session file: **absent**
- iai recall JSON parse: **True**
- iai recall source: `daemon-down-full`
- recall count: `5`
- known memory marker found: **True**

This is not a valid completed Start Orion state.

## Incident snapshot after attempted Stop Orion

The operator clicked Stop Orion, then ran a read-only resource snapshot. Hermes remained reachable while Ollama remained down.

System memory:

- Total visible RAM: **15.88 GB**
- Free RAM at snapshot time: **8.41 GB**

Top working-set processes at snapshot time included Firefox, Explorer, Memory Compression, Malwarebytes, Task Manager, and one Python process; no Ollama process was present among the top consumers.

Windows event checks:

- System Event ID 2004 (resource exhaustion) in prior hour: **none returned**
- Recent Application events matching `ollama`, `out of memory`, or `resource exhaustion`: **none returned**

Therefore there is no current evidence of a Windows hard out-of-memory/resource-exhaustion event or recorded Ollama crash. A transient model-load or paging/GPU-memory pressure event remains possible but unproven because the snapshot was taken after the severe slowdown and after Ollama was no longer available.

## Launcher defect identified by source inspection

Current `scripts/operator/Start-Orion.ps1` starts Ollama, then starts Hermes, then writes `launcher-session.json`. In its `catch` block it stops Orion-owned Ollama if present, but it does **not** stop a Hermes gateway that may already have been started successfully before a later failure.

This means a failure after Hermes has started can leave:

- Hermes running,
- Ollama stopped by rollback,
- no launcher session file.

That topology matches the observed incident state. The launcher rollback defect is real and must be corrected before the next Start Orion acceptance attempt, although it does not by itself identify the original trigger for the failure or the machine-wide slowdown.

## Disposition

- Post-reboot Start Orion acceptance: **FAIL / BLOCKED**
- OR-LIFE-005: **OPEN**
- Discord acceptance: **not run**
- Further restart/logoff tests: **paused**
- Required next step: restore a clean off state, capture the exact Start Orion failure/exit path and resource behavior, then patch launcher rollback so Hermes is also stopped if Start Orion fails after spawning it.

Core Intent Preservation: **PRESERVED** — no supervisor or alternate lifecycle system is introduced; this is rollback hardening and root-cause investigation within the existing one-shot launcher design.
