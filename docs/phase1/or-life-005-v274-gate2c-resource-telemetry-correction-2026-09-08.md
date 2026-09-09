# OR-LIFE-005 — v2.7.4 Gate 2C session/resource snapshot and telemetry correction

Date: 2026-09-08
Candidate: Orion operator controls v2.7.4-candidate1

## Gate 2C result

PASS for candidate session ownership and current runtime/resource snapshot.

Current runtime state during Gate 2C:
- Hermes API remained healthy from Gate 2B.
- Candidate session record schema 4 validated on the current boot.
- Orion-owned Ollama identity was recorded and matched the live process exactly.
- iai Scheduled Task state: Running.
- One iai wrapper-like Node process observed.
- Hermes Scheduled Task remained Ready; manual-off LogonTrigger policy remained unchanged from prior gates.

Candidate session evidence:
- sameBoot: true
- ownedOllamaRecorded: true
- ownedOllamaIdentityLive: true
- ownedOllamaPid: 25900
- ownedOllamaImage: C:\Users\spill\AppData\Local\Programs\Ollama\ollama.exe

## Current resource snapshot

- Total RAM: 16,264 MB
- Free RAM: 5,473 MB
- Pagefile: D:\pagefile.sys, 20,480 MB allocated, 60 MB current usage, 60 MB peak usage
- NVIDIA GeForce RTX 3070: 8,192 MiB total VRAM, 2,512 MiB used, 5,506 MiB free, 11% GPU utilization
- `ollama ps` returned no loaded model at snapshot time.

This means the successful Gate 2B cold start started the Ollama server and Hermes gateway but had not yet loaded the configured model. The first real inference/model load remains the important resource-pressure validation point.

## Gate 2B telemetry correction

The Gate 2B observer CSV is not valid for numeric interpretation. It formatted numeric fields with PowerShell `N0`, which inserted thousands separators (commas) into an unquoted comma-separated line. `Import-Csv` therefore shifted columns. The previously reported values such as `Minimum free RAM MB: 264`, `ollama_count: 20`, and similar timeline fields are parser artifacts and must not be used as resource evidence.

Authoritative evidence is the direct Gate 2C snapshot above. Gate 2B remains a functional launcher PASS; its resource telemetry summary is superseded/invalidated.

## Next validation

Run one first-inference / Discord + ambient-recall roundtrip while a corrected observer records raw numeric CSV values (no thousands separators), including RAM/pagefile and GPU VRAM when available. Then inspect candidate Stop behavior.

No lifecycle command was issued during Gate 2C.
