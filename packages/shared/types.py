import enum


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY_SCHEDULED = "retry_scheduled"
    CANCELLED = "cancelled"
    DEAD = "dead"  # moved to DLQ

    @property
    def is_terminal(self) -> bool:
        return self in (self.COMPLETED, self.CANCELLED, self.DEAD)

    @property
    def is_retryable(self) -> bool:
        return self == self.FAILED


class RetryStrategy(str, enum.Enum):
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


class WorkerStatus(str, enum.Enum):
    ONLINE = "online"
    DRAINING = "draining"  # finishing current jobs, accepting no new ones
    OFFLINE = "offline"
    LOST = "lost"  # missed heartbeats
