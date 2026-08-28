# P4-02B1A — Autonomous Observer Basis

**Status: controlling observation basis for the production external-idle candidate**

Date: 2026-08-28 UTC

This note refines the generic autonomous acceptance wording for the actual production topology where the COMPANION MCP wrapper remains intentionally fresh.

## Native iai path with a live wrapper

Pinned iai source keeps a fresh wrapper higher priority until an entry arm can actually lead to sleep. In the accepted production topology, the relevant nightly arm is `window_deep_idle` using real OS/host-idle evidence.

Accordingly, the expected production path is not necessarily a visible `WAKE -> DROWSY` transition at exactly five minutes of host input idle. With the wrapper still fresh, iai may remain `WAKE` until the native 30-minute window-deep-idle condition is armed and `sleep_eligible` is true. At that point the FSM must still climb the normal ladder:

1. `WAKE -> DROWSY` with persisted reason `drowsy_on_armed_entry`;
2. on the following eligible tick, `DROWSY -> SLEEP` with persisted reason `sleep_on_window_deep_idle`;
3. after the sleep cycle completes while still idle, `SLEEP -> HIBERNATION` via the native `SLEEP_CYCLE_DONE` path.

The generic non-wrapper path (`drowsy_on_idle_5min` then `sleep_on_idle_30min`) remains valid when scanner activity is absent. The production observer accepts either native path but must record the exact persisted triggers.

## Why this matters

The live-wrapper path is deliberate upstream behavior. Treating the absence of a five-minute DROWSY transition as failure would contradict iai's own decision function: a live wrapper returns `wake_refresh` unless the starvation/window arm is both active and structurally sleep-eligible. When armed while still in `WAKE`, iai explicitly emits `drowsy_on_armed_entry` because `IDLE_30MIN` is accepted by the FSM only from `DROWSY`.

## Observation safety

The production observer is read-only:

- no Brain/manual lifecycle controls;
- no daemon socket request;
- no threshold/environment mutation;
- no lifecycle/store edits;
- no container/service restart;
- no wrapper cleanup;
- no host-idle producer restart.

It validates the deployed core identity, the live host-idle producer provenance/freshness, iai's external-idle source, fresh wrapper presence, and current consolidation-window membership before waiting for authoritative lifecycle-event rows.

P4-02B1A remains open after autonomous hibernation evidence until the separate foreground-wake/activity acceptance is completed.
