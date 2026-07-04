"""Tests for the API response envelope.

The envelope is our contract with frontend consumers. If we break it,
every API consumer breaks.
"""
import pytest

from packages.shared.envelope import ApiResponse, PaginationMeta


class TestApiResponse:
    def test_ok_response(self):
        resp = ApiResponse.ok({"id": "123"})
        assert resp.success is True
        assert resp.data == {"id": "123"}
        assert resp.error is None

    def test_ok_with_pagination(self):
        pagination = PaginationMeta(page=1, per_page=50, total=100, total_pages=2)
        resp = ApiResponse.ok([1, 2, 3], pagination=pagination)
        assert resp.pagination.total == 100
        assert resp.pagination.total_pages == 2

    def test_fail_response(self):
        resp = ApiResponse.fail("Not found", error_code="NOT_FOUND")
        assert resp.success is False
        assert resp.error == "Not found"
        assert resp.error_code == "NOT_FOUND"
        assert resp.data is None

    def test_ok_with_meta(self):
        resp = ApiResponse.ok({"id": "1"}, request_duration_ms=42)
        assert resp.meta["request_duration_ms"] == 42
