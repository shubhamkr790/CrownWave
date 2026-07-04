# ADR-003: Worker Liveness and Crash Recovery

## Status

Accepted

## Context

Workers can crash without cleaning up their claimed jobs. Without recovery, these jobs would remain in `claimed` or `running` state forever ("zombie jobs").

Options considered:
1. **Heartbeat-based detection** with timeout threshold
2. **Lease-based claiming** with automatic expiry
3. **External monitoring** (health check endpoints + orchestrator)

## Decision

Heartbeat-based detection with startup recovery.

## How It Works

1. Workers send periodic heartbeats (default: every 30s) updating `workers.last_heartbeat_at`
2. On each scheduler tick, `detect_lost_workers()` finds workers whose last heartbeat exceeds the timeout (default: 90s)
3. Lost workers are marked `status = 'lost'` and a `worker_events` entry is recorded
4. `recover_stale_claims()` re-queues any jobs with `claimed_at` older than the timeout
5. On startup, a new worker also runs recovery to clean up anything left from a previous crash

## Rationale

- Heartbeats are simple to implement and well-understood
- The timeout must be significantly larger than the heartbeat interval (3x by default) to avoid false positives from network blips or GC pauses
- Recording recovery in `worker_events` provides an audit trail
- Startup recovery handles the case where no scheduler was running during the crash window

## Consequences

- A crashed worker's jobs are unavailable for `worker_heartbeat_timeout_sec` (90s default)
- Long-running jobs may be incorrectly recovered — future versions should support job-level heartbeats
- The scheduler is a single point of responsibility for recovery (acceptable for current scale)
