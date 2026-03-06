"""Tests for request tracing utilities."""

from __future__ import annotations

from {{ cookiecutter.package_name }}.utils.tracing import (
    correlation_id_var,
    generate_id,
    get_correlation_id,
    get_request_id,
    request_id_var,
    trace_request,
)


class TestGenerateId:
    def test_length(self) -> None:
        assert len(generate_id()) == 16

    def test_unique(self) -> None:
        assert generate_id() != generate_id()


class TestTraceRequest:
    def test_sets_ids(self) -> None:
        with trace_request():
            assert get_request_id() != ""
            assert get_correlation_id() != ""

    def test_resets_on_exit(self) -> None:
        with trace_request():
            pass
        assert get_request_id() == ""
        assert get_correlation_id() == ""

    def test_accepts_correlation_id(self) -> None:
        with trace_request(correlation_id="abc123"):
            assert get_correlation_id() == "abc123"

    def test_generates_correlation_id_when_none(self) -> None:
        with trace_request():
            cid = get_correlation_id()
            assert len(cid) == 16

    def test_nesting(self) -> None:
        with trace_request(correlation_id="outer"):
            outer_rid = get_request_id()
            with trace_request(correlation_id="inner"):
                assert get_correlation_id() == "inner"
                assert get_request_id() != outer_rid
            assert get_correlation_id() == "outer"
            assert get_request_id() == outer_rid

    def test_resets_after_exception(self) -> None:
        try:
            with trace_request():
                raise ValueError("boom")
        except ValueError:
            pass
        assert get_request_id() == ""
