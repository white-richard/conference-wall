"""Tests for HTTP server module."""

import io
import socket
import threading
import time
import urllib.request
from pathlib import Path

import pytest

from confwall.server import ConfwallRequestHandler, run_server


def test_run_server_nonexistent_directory(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        run_server(tmp_path / "nonexistent")


def test_confwall_request_handler_cache_headers():
    class DummyHandler(ConfwallRequestHandler):
        def __init__(self, path):
            self.path = path
            self.request_version = "HTTP/1.1"
            self._headers_buffer = []
            self.wfile = io.BytesIO()
            self.headers_sent = {}

        def send_header(self, keyword, value):
            self.headers_sent[keyword] = value

    h_html = DummyHandler("/index.html")
    h_html.end_headers()
    assert h_html.headers_sent.get("Cache-Control") == "no-cache, no-store, must-revalidate"

    h_js = DummyHandler("/app.js")
    h_js.end_headers()
    assert h_js.headers_sent.get("Cache-Control") == "no-cache, no-store, must-revalidate"

    h_css = DummyHandler("/style.css")
    h_css.end_headers()
    assert h_css.headers_sent.get("Cache-Control") == "no-cache, no-store, must-revalidate"

    h_img = DummyHandler("/images/test.jpg")
    h_img.end_headers()
    assert h_img.headers_sent.get("Cache-Control") == "public, max-age=31536000, immutable"


def test_run_server_live_request(tmp_path: Path):
    build_dir = tmp_path / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "index.html").write_text("<h1>Confwall</h1>", encoding="utf-8")

    images_dir = build_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    (images_dir / "test.jpg").write_bytes(b"jpg_data")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    def start_srv():
        try:
            run_server(build_dir, host="127.0.0.1", port=port)
        except Exception:
            pass

    t = threading.Thread(target=start_srv, daemon=True)
    t.start()

    time.sleep(0.3)

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/index.html") as req_html:
        assert req_html.status == 200
        assert "no-cache" in req_html.headers.get("Cache-Control", "")

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/images/test.jpg") as req_img:
        assert req_img.status == 200
        assert "max-age=31536000" in req_img.headers.get("Cache-Control", "")
