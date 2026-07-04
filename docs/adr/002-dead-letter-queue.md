# ADR-002: Dead Letter Queue Design

## Status

Accepted

## Context

When a job exhausts all retry attempts, it needs to go somewhere operators can inspect and act on it. The options:

1. **Mark on the jobs table** — add a `is_dead_lettered` flag
2. **Separate DLQ table with FK only** — just store a reference to the job
3. **Separate DLQ table with denormalized data**

## Decision

Separate `dead_letter_queue` table with denormalized fields (job name, payload, error, attempt count).

## Rationale

- The DLQ serves a different access pattern than the jobs table. Operators filter by error, replay entries, and acknowledge them. Mixing this with the main jobs table would either bloat the jobs model or require complex queries.
- Denormalization ensures the DLQ stays useful even if original jobs are archived or purged. In production, the jobs table might be pruned aggressively, but DLQ entries need longer retention.
- The `is_resolved` flag and `resolved_at` timestamp support a workflow: inspect → replay or acknowledge → close.

## Consequences

- Data duplication between `jobs` and `dead_letter_queue`
- Replaying a DLQ entry updates the original job row (if it still exists)
- DLQ entries accumulate and need their own retention policy
