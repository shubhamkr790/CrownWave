# ADR-001: Job Claiming Strategy

## Status

Accepted

## Context

Workers need to atomically claim jobs from a shared queue. Multiple workers running concurrently must not claim the same job. The primary options are:

1. **Redis-based queuing** (BRPOPLPUSH or Streams)
2. **Postgres advisory locks**
3. **`SELECT ... FOR UPDATE SKIP LOCKED`**
4. **Optimistic locking with version column**

## Decision

We use `SELECT ... FOR UPDATE SKIP LOCKED` for job claiming.

## Rationale

- **SKIP LOCKED** is purpose-built for this use case. It's how Stripe, Uber, and GraphQL Hive implement queue-based job systems on Postgres.
- Workers don't block each other. Each worker grabs the next _unlocked_ row, skipping any rows already being claimed by another transaction. This gives near-linear throughput scaling with worker count.
- We get ACID guarantees for free — the claim and status update happen in one transaction.
- No additional infrastructure (Redis Streams would require maintaining a separate stateful system).

**Why not NOWAIT?** NOWAIT raises an exception if the row is locked, requiring retry logic in the application. SKIP LOCKED silently moves to the next row, which is simpler and gives better throughput for queue-like workloads.

**Why not Redis?** Redis would add operational complexity and a second data store. We'd need to synchronize job metadata between Redis and Postgres. For our throughput requirements (hundreds of jobs/sec), Postgres handles it fine. If we ever need thousands/sec, we'd consider Redis Streams as a write-ahead buffer.

## Consequences

- Job claiming requires Postgres (not portable to MySQL without modification)
- Claim queries need careful index design (the `ix_jobs_claimable` partial index)
- Connection pooling must be sized for concurrent worker transactions
