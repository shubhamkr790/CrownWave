"""Tests for domain error mapping.

Verifies that each error type carries the right HTTP status code and
error code. The API exception handler relies on these to produce
correct responses.
"""
import pytest

from packages.shared.errors import (
    AuthenticationError,
    ConflictError,
    CronwaveError,
    JobStateError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)


class TestDomainErrors:
    def test_not_found_includes_resource(self):
        err = NotFoundError("Queue", "abc-123")
        assert "Queue" in err.message
        assert "abc-123" in err.message
        assert err.status_code == 404

    def test_conflict_error(self):
        err = ConflictError("Duplicate idempotency key")
        assert err.status_code == 409

    def test_validation_error(self):
        err = ValidationError("Invalid cron expression")
        assert err.status_code == 422
        assert err.error_code == "VALIDATION_ERROR"

    def test_permission_denied(self):
        err = PermissionDeniedError()
        assert err.status_code == 403

    def test_auth_error(self):
        err = AuthenticationError()
        assert err.status_code == 401

    def test_job_state_error(self):
        err = JobStateError("Cannot complete a cancelled job")
        assert err.status_code == 409
        assert err.error_code == "INVALID_STATE_TRANSITION"

    def test_base_error(self):
        err = CronwaveError("something broke")
        assert err.status_code == 500
