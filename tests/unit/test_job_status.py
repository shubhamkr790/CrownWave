"""Tests for job state machine transitions.

Verifies that JobStatus properties correctly identify terminal
and retryable states — important because the worker uses these
to decide whether to retry or dead-letter a job.
"""
import pytest

from packages.shared.types import JobStatus


class TestJobStatus:
    def test_terminal_states(self):
        terminal = [s for s in JobStatus if s.is_terminal]
        assert set(terminal) == {JobStatus.COMPLETED, JobStatus.CANCELLED, JobStatus.DEAD}

    def test_non_terminal_states(self):
        non_terminal = [s for s in JobStatus if not s.is_terminal]
        assert JobStatus.QUEUED in non_terminal
        assert JobStatus.RUNNING in non_terminal
        assert JobStatus.RETRY_SCHEDULED in non_terminal

    def test_retryable_only_when_failed(self):
        assert JobStatus.FAILED.is_retryable
        assert not JobStatus.COMPLETED.is_retryable
        assert not JobStatus.RUNNING.is_retryable

    def test_string_values(self):
        """Enum values should be lowercase strings matching the DB column."""
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.RETRY_SCHEDULED.value == "retry_scheduled"
