# Hermes v0.22.5 Startup Timing Diagnostic Result

Status: **PASS — startup reached HTTP readiness within the existing 90-second gate**

Date: 2026-10-30

Candidate:

- upstream release: `v0.22.5`
- exact candidate commit: `bf0203a794a07aac3ff764972ab9087baa4e4f4e`
- migration PR: #81

## Reason for diagnostic

The preceding isolated session/profile v2 attempt launched the candidate but did not reach `/health` within the 90-second readiness window. Its log showed a live standalone process and later startup activity, but the session-resource contract never began. The same run also reported a production watched-state change because the older harness treated live runtime file mtime/size changes as a mutation oracle.

That result was therefore a diagnostic breakpoint, not a Hermes session failure and not proof of production mutation.

## Diagnostic result

A dedicated startup-only rerun on the same candidate/runtime reached proxy-disabled loopback HTTP readiness in **8.285 seconds**:

```text
STARTUP_SAMPLE=elapsed_s=2.1|health=UNREACHABLE|root_poll=None|alive_processes=2|pids=16832,26832|threads=14|rss_bytes=60968960|cpu_seconds=0.844|log_bytes=0
COLD_START_HTTP_READY=PASS|elapsed_s=8.285
COLD_START_CLASSIFICATION=READY_WITHIN_LEGACY_90S
POST_READY_HTTP_STABILITY=PASS|samples=8
POST_READY_PROCESS_ALIVE=PASS
```

The startup timing diagnostic itself passed:

```text
STARTUP_TIMING_DIAGNOSTIC=PASS
PRODUCTION_HERMES_MUTATED=false
COMPANION_STATIC_CONFIG_MUTATED=false
PRODUCTION_RUNTIME_RESTARTED=false
```

## Production safety evidence

The corrected observer separated immutable/identity-sensitive production evidence from normal live-runtime churn:

```text
PRODUCTION_8642_HEALTH_BASELINE=HTTP_200|status=ok
PRODUCTION_8642_HEALTH_AFTER=HTTP_200|status=ok
PRODUCTION_VOLATILE_RUNTIME_CHANGED=NONE
PRODUCTION_VOLATILE_RUNTIME_CHANGE_IS_MUTATION_ORACLE=false
PRODUCTION_STATIC_CONFIG_UNCHANGED=PASS
PRODUCTION_GATEWAY_PID_IDENTITY_UNCHANGED=PASS
CANDIDATE_GIT_STATUS_UNCHANGED=PASS
```

No production restart, provider/model request, memory request, session mutation, STT call, or TTS call occurred.

## Classification

The earlier 90-second readiness miss is currently classified as **intermittent/unresolved startup variance**. It is not reproduced by this controlled diagnostic and therefore is not sufficient by itself to reject v0.22.5. It also is not erased: another readiness miss in a later isolated gate should be treated as recurrence evidence and investigated rather than hidden by simply extending timeouts.

Upstream issue #144883 remains relevant background because it describes profile-scope synchronous I/O stalls that can block the gateway event loop, but this diagnostic did not reproduce an exit-75 watchdog event and does not establish that issue as the cause of the earlier miss.

## Next gate

Resume the isolated session/profile contract with a v3 observer that:

- retains the structural scratch-profile identity check and read-only SQLite persistence verification from v2;
- retains the existing 90-second readiness acceptance boundary;
- emits bounded startup samples while waiting so a recurrence is diagnosable;
- treats production static configuration and gateway PID identity as mutation-sensitive evidence;
- treats normal volatile runtime mtime/size changes as observational evidence only;
- performs no chat/model/memory/STT/TTS request.
