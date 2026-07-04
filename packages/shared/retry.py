"""Retry delay calculation.

Each strategy computes the delay differently:
- Fixed: always the same delay
- Linear: delay grows linearly with attempt number
- Exponential: delay doubles each attempt (with a cap)

We use a simple function dispatch instead of a class hierarchy.
A strategy pattern with inheritance would be overkill for three
stateless functions that take the same arguments.
"""
from packages.shared.types import RetryStrategy


def calculate_retry_delay(
    strategy: RetryStrategy,
    attempt: int,
    base_delay_sec: int,
    max_delay_sec: int,
) -> int:
    """Returns the delay in seconds before the next retry."""
    calculators = {
        RetryStrategy.FIXED: _fixed_delay,
        RetryStrategy.LINEAR: _linear_delay,
        RetryStrategy.EXPONENTIAL: _exponential_delay,
    }
    delay = calculators[strategy](attempt, base_delay_sec)
    return min(delay, max_delay_sec)


def _fixed_delay(attempt: int, base: int) -> int:
    return base


def _linear_delay(attempt: int, base: int) -> int:
    return base * attempt


def _exponential_delay(attempt: int, base: int) -> int:
    # 2^(attempt-1) gives: 1x, 2x, 4x, 8x, ...
    return base * (2 ** (attempt - 1))
