# P4-04A — Bounded Hermes gateway audio compatibility patch

**Status:** IMPLEMENTED IN SOURCE CONTROL / NOT APPLIED TO RUNTIME  
**Date:** 2026-09-15  
**Issue:** #17  
**Blocked consumer:** draft PR #16 (`feature/orion-phase4-p4-04-push-to-talk`)  
**Accepted Hermes:** `v2026.8.27` / package `0.20.6` / commit `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`

## Why this ticket exists

P4-04/P4-05 needs browser microphone audio to be transcribed by Hermes and normal Hermes replies to be synthesized by Hermes TTS. Orion already talks to the authenticated Hermes API server on loopback port 8642.

The accepted Hermes gateway exposes session, streaming, run-control, model, skill, and toolset APIs, but its capabilities contract explicitly reports:

- `audio_api: false`
- `realtime_voice: false`

Hermes already contains its own STT and TTS implementations. The gap is therefore an API-surface gap, not a missing speech-engine gap.

A check of the newer stable Hermes release and current upstream did not identify a gateway release that closes this specific gap. Upgrading Hermes solely for P4-04A is therefore not justified by the evidence.

## Decision

Add only two authenticated routes to the already accepted gateway:

- `POST /api/audio/transcribe`
- `POST /api/audio/speak`

The patch reuses Hermes' existing `transcribe_recording()` and `text_to_speech_tool()` implementations. It does not add another listener, another voice service, browser-provider credentials, a Web Speech API path, or realtime/full-duplex voice transport.

After the patch is present, `/v1/capabilities` advertises:

- `audio_api: true`
- `realtime_voice: false`

That distinction is intentional. P4-04A enables bounded HTTP STT/TTS relay only.

## Source identity and fail-closed rule

The patch target is exactly:

- repository: `NousResearch/hermes-agent`
- commit: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- file: `gateway/platforms/api_server.py`
- expected Git blob SHA-1: `980659c9343d2975040f304e05bf97fa95f6a046`

`scripts/phase4/p4-04a-hermes-audio-gateway.py` computes the Git blob identity from the installed file bytes itself. `--apply` refuses to modify any file whose blob does not exactly match the accepted source.

## Patch behavior

The source-controlled patcher makes five deterministic changes:

1. documents the two audio endpoints in the module endpoint list;
2. registers the two POST routes in `_http_route_table()` so normal multiplex route mirroring also applies;
3. changes only the API capability flag `audio_api` from false to true;
4. advertises both audio endpoints in the capability endpoint map;
5. inserts two bounded authenticated handlers before the existing browser-control handler section.

### Transcription handler

- requires the existing gateway Bearer authentication;
- accepts only a base64 data URL with an allowlisted audio MIME type;
- requires declared/requested MIME types to agree;
- caps decoded audio at 4 MiB;
- writes a temporary audio file and deletes it in `finally`;
- re-enters the gateway's selected profile scope in the worker thread;
- calls Hermes `tools.voice_mode.transcribe_recording()`;
- returns only `ok`, `transcript`, and `no_speech`;
- redacts exception text through the gateway's existing redaction helper.

The gateway validates the declared/requested MIME contract, encoding, and decoded-size bound, but it does not independently inspect container magic bytes before handing the temporary file to Hermes. A corrupted or mislabeled payload therefore fails inside `transcribe_recording()` and is surfaced as a bounded `502`. This is an accepted local-relay tradeoff for P4-04A rather than an additional media-sniffing layer.

### Speech handler

- requires the existing gateway Bearer authentication;
- caps input at 4,000 characters;
- re-enters the selected profile scope in the worker thread;
- calls Hermes `tools.tts_tool.text_to_speech_tool()`;
- validates the returned media path through Hermes' existing `validate_media_delivery_path()` guard;
- caps returned audio at 16 MiB;
- returns only a browser-playable audio data URL and MIME type;
- never returns TTS-provider credentials or configuration secrets.

## Apply / rollback safety

The Python patcher:

- has a built-in `--self-test` transformation/compile test;
- compile-checks the full patched `api_server.py` before replacement;
- writes a byte-for-byte `.orion-p4-04a.bak` backup;
- writes a JSON manifest containing pre/post SHA-256 and accepted source identity;
- replaces the target only after verification;
- refuses an ambiguous second apply;
- rolls back only when the manifest and backup match this patch ID and the accepted pre-patch blob;
- verifies the restored Git blob after rollback and removes its patch sidecars.

A leftover backup or manifest is deliberately treated as an ambiguous state. Any later `Apply` refuses to continue until those sidecars are reconciled manually. This includes the case where an interrupted or failed rollback leaves a sidecar behind. The first diagnostic is to compare the manifest's `pre_git_blob_sha1` with the live target's current Git blob. If the live file still matches `pre_git_blob_sha1`, the patch did not land and the sidecars are residual pre-replace state that may be cleared after confirming the manifest/backup belong to this patch. If the live file matches the expected patched content, treat the installation as patched and reconcile the sidecars accordingly. If the live file matches neither the pre-patch blob nor the expected patched content, stop and investigate before touching any sidecar because the target may have been modified outside this tool's control. The stop is a fail-closed recovery boundary, not an apply bug.

The PowerShell wrapper `scripts/phase4/p4-04a-hermes-audio-gateway.ps1` can discover the installed Hermes module through the Hermes Python environment. It refuses `Apply` or `Rollback` while something is listening on port 8642 and never starts or restarts Hermes automatically.

## Source-control validation completed

- Python patcher built-in self-test: PASS
- synthetic patched module compile check: PASS
- accepted upstream route/capability anchors reviewed at the pinned commit
- no runtime file has been modified
- no service has been restarted
- no microphone/STT/TTS request has been sent

PowerShell syntax must be parse-checked on Windows before first execution, per Orion operator procedure.

## Runtime acceptance sequence

Runtime application is a separate operator-controlled step. Before P4-04A can close:

1. stop Orion/Hermes so port 8642 is not listening;
2. parse-check the PowerShell wrapper;
3. run `SelfTest`;
4. run `Verify` and confirm the installed source matches the expected accepted Git blob;
5. run `Apply`;
6. restart through the normal Orion lifecycle only;
7. verify authenticated `/v1/capabilities` reports `audio_api: true` and `realtime_voice: false`;
8. run focused authenticated TTS and STT smoke using the COMPANION profile;
9. confirm no secret value is returned or logged;
10. return to draft PR #16 for JLab push-to-talk, same-session, progressive speech, privacy-state, fallback, and interruption validation.

If any post-apply gate fails, stop Hermes and use the wrapper's `Rollback` action before further diagnosis.

## Explicitly out of scope

- Hermes dependency upgrade
- second Hermes dashboard/web-server process
- wake changes or custom-model v3
- realtime voice websocket/full-duplex transport
- separate Orion STT/TTS engines
- Web Speech API
- lifecycle changes
- iai changes

P4-04A is a compatibility bridge for the accepted dependency, not a claim that Hermes upstream now natively exposes realtime voice on the API server.
