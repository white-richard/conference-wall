"""Tests for http_client module."""

import pytest
import requests

from confwall.http_client import HttpClient


class MockResponse:

    def __init__(self, status_code: int, content: bytes = b"", json_data: dict | list | None = None):
        self.status_code = status_code
        self.content = content
        self._json_data = json_data

    def json(self):
        if self._json_data is not None:
            return self._json_data
        raise ValueError("No JSON")

    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise requests.HTTPError(response=self)


def test_http_client_success(monkeypatch):
    client = HttpClient()

    def mock_request(*args, **kwargs):
        return MockResponse(200, content=b"hello", json_data={"key": "val"})

    monkeypatch.setattr(client.session, "request", mock_request)

    assert client.get_bytes("https://example.com") == b"hello"
    assert client.get_json("https://example.com") == {"key": "val"}


def test_http_client_404_no_retry(monkeypatch):
    client = HttpClient()
    calls = 0

    def mock_request(*args, **kwargs):
        nonlocal calls
        calls += 1
        return MockResponse(404)

    monkeypatch.setattr(client.session, "request", mock_request)

    with pytest.raises(RuntimeError) as exc_info:
        client.get_bytes("https://example.com/missing")
    assert "404" in str(exc_info.value)
    assert calls == 1  # No retries on 404


def test_http_client_500_retry_failure(monkeypatch):
    client = HttpClient()
    calls = 0

    def mock_request(*args, **kwargs):
        nonlocal calls
        calls += 1
        return MockResponse(500)

    monkeypatch.setattr(client.session, "request", mock_request)

    with pytest.raises(RuntimeError):
        client.get_bytes("https://example.com/error")
    assert calls == 3


def test_http_client_timeout_retry(monkeypatch):
    client = HttpClient()
    calls = 0

    def mock_request(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise requests.Timeout("connection timed out")

    monkeypatch.setattr(client.session, "request", mock_request)

    with pytest.raises(RuntimeError) as exc_info:
        client.get_bytes("https://example.com/timeout")
    assert "timed out" in str(exc_info.value)
    assert calls == 3
