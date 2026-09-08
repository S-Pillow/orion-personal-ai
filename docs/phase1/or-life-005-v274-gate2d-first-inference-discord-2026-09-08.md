# OR-LIFE-005 — v2.7.4 Gate 2D First Inference / Discord / Ambient Recall

Date: 2026-09-08
Candidate: Orion Operator Controls v2.7.4-candidate1
Branch: feature/orion-start-v272-lifecycle-safety

## Result

Gate 2D first-inference / Discord roundtrip / ambient-memory validation is functionally PASS with one non-blocking response-format note.

### Discord / model path

- `/new` started a fresh conversation and reported model `qwen3.5-hermes:9b`, custom provider, 65k context, endpoint `http://localhost:11434/v1`.
- The first plain-text memory query before `/new` produced `TOOL_NOT_CALLED`; after `/new`, a fresh query completed.
- Hermes emitted the existing informational message that no Discord home channel is configured. This is unrelated to lifecycle control and did not block the query.
- The post-`/new` response surfaced both known Orion memory markers, including the required target `ORION_CAPTURE_FRESH_GATEWAY_20260829`.
- The response did not obey the synthetic prompt's request to return only the marker, so the local PowerShell exact-string check returned False. This is classified as a response-format failure only, not an ambient-recall failure: the target marker was demonstrably recalled in the Discord response.
- Additional pasted response text was accidentally entered at the PowerShell prompt afterward, causing ordinary `CommandNotFoundException` messages. No lifecycle command was executed by those lines.

### Corrected first-inference telemetry

The corrected CSV observer used `Export-Csv` rather than manual comma-formatted rows.

83 samples were captured across the first Discord/model inference window:

- minimum free RAM: 4,549 MB
- maximum pagefile used: 88 MB
- maximum GPU memory used: 2,653 MiB
- minimum GPU memory free: 5,365 MiB

After inference, `ollama ps` showed:

- model: `qwen3.5-hermes:9b`
- size: 7.1 GB
- processor placement: 20% CPU / 80% GPU
- context: 65,536

No severe system slowdown was reproduced during this controlled cold start plus first model inference. This weakens the earlier hypothesis that normal candidate startup/model load necessarily causes the prior extreme UI lag, but it does not establish the root cause of that earlier incident.

## Acceptance interpretation

- candidate cold start: PASS (from Gate 2B)
- exact session/Ollama identity: PASS (from Gate 2C)
- first real model load/inference: PASS
- Discord roundtrip after `/new`: PASS
- ambient iai memory recall of accepted marker: PASS
- exact-response formatting (`reply with only marker`): FAIL, non-blocking for lifecycle/memory acceptance
- severe resource-pressure reproduction: NOT REPRODUCED

## Next step

Proceed directly to candidate Stop validation while this same accepted session is running. Do not use the legacy desktop Stop shortcut.
