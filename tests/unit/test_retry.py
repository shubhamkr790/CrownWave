"""Tests for retry delay calculation.

These are pure unit tests — no database, no I/O.
The retry calculator is one of the few places where getting the
math wrong would cause real production issues (jobs retrying too
fast could DDoS downstream services).
"""
import pytest

from packages.shared.retry import calculate_retry_delay
from packages.shared.types import RetryStrategy


class TestFixedRetry:
    def test_always_same_delay(self):
        for attempt in range(1, 6):
            delay = calculate_retry_delay(
                RetryStrategy.FIXED, attempt=attempt, base_delay_sec=30, max_delay_sec=3600
            )
            assert delay == 30

    def test_respects_max_delay(self):
        delay = calculate_retry_delay(
            RetryStrategy.FIXED, attempt=1, base_delay_sec=5000, max_delay_sec=3600
        )
        assert delay == 3600


class TestLinearRetry:
    def test_grows_linearly(self):
        delays = [
            calculate_retry_delay(RetryStrategy.LINEAR, attempt=i, base_delay_sec=10, max_delay_sec=3600)
            for i in range(1, 5)
        ]
        assert delays == [10, 20, 30, 40]

    def test_caps_at_max(self):
        delay = calculate_retry_delay(
            RetryStrategy.LINEAR, attempt=100, base_delay_sec=60, max_delay_sec=300
        )
        assert delay == 300


class TestExponentialRetry:
    def test_doubles_each_attempt(self):
        delays = [
            calculate_retry_delay(RetryStrategy.EXPONENTIAL, attempt=i, base_delay_sec=10, max_delay_sec=10000)
            for i in range(1, 5)
        ]
        # 10 * 2^0, 10 * 2^1, 10 * 2^2, 10 * 2^3
        assert delays == [10, 20, 40, 80]

    def test_caps_at_max(self):
        delay = calculate_retry_delay(
            RetryStrategy.EXPONENTIAL, attempt=20, base_delay_sec=60, max_delay_sec=3600
        )
        assert delay == 3600

    def test_first_attempt_equals_base(self):
        delay = calculate_retry_delay(
            RetryStrategy.EXPONENTIAL, attempt=1, base_delay_sec=30, max_delay_sec=3600
        )
        assert delay == 30
