# OR-LIFE-005 Post-Reboot Start Anomaly — 2026-09-08

Status: **BLOCKED / ROOT CAUSE PENDING**

Controlling intent: after a clean manual-off reboot/login, `Start Orion` should start the local model provider if needed, start Hermes COMPANION, establish a healthy backend, record local-provider ownership, and return the system to a responsive steady state without a resident supervisor.

## Operator-observed responsiveness degradation

After invoking Start Orion post-reboot, the operator reported severe machine-wide slowdown:

- PowerShell prompt did not return normally.
- A restarted PowerShell instance took more than 30 seconds for pasted input to appear.
- Task Manager took a long time to open.

This is material operator-impact evidence and blocks acceptance until explained.

## Runtime verification after the anomalous start

Observed:

- Hermes API healthy on `127.0.0.1:8642`: **True**
- Ollama API healthy on `127.0.0.1:11434`: **False**
- `%LOCALAPPDATA%\Orion\operator\launcher-session.json` present: **False**
- iai recall JSON parse: **True**
- iai recall `_source`: `daemon-down-full`
- recall count: `5`
- known marker `ORION_CAPTURE_FRESH_GATEWAY_20260829` found: **True**

The check was accidentally pasted twice after severe console lag; the second run reproduced the same essential state: Hermes healthy, Ollama unavailable, launcher session absent, memory recall successful through daemon-independent fallback.

## Source review

Current `scripts/operator/Start-Orion.ps1` behavior was reviewed from `main`.

Relevant rollback gap:

- Start Orion may start Ollama and then Hermes.
- Session state is written only after Hermes health succeeds.
- In the outer `catch`, the script attempts to stop Orion-started Ollama.
- The outer `catch` does **not** stop a Hermes gateway that may already have started successfully.

Therefore, a failure after Hermes becomes healthy but before successful session-state persistence can leave exactly this degraded topology: Hermes remains up, Ollama may be stopped by rollback, and no launcher ownership state exists. This source-level gap matches the observed final state, but it does **not** by itself identify the underlying exception that triggered rollback.

## Current disposition

- Post-reboot manual-off boot state: previously **PASS**.
- Post-reboot Start Orion recovery: **BLOCKED**.
- Discord acceptance: **do not run** until runtime is healthy and responsiveness issue is understood.
- Additional reboot/logoff tests: **do not run** yet.
- Core Intent Preservation: **PRESERVED** by stopping acceptance and diagnosing rather than masking the failure.

Next step: return Orion to a clean off state, then gather bounded read-only resource/process evidence before any further launcher execution.
