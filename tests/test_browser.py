"""Playwright browser end-to-end smoke test for confwall."""

import json
import socket
import threading
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from confwall.server import ConfwallRequestHandler, ThreadingHTTPServer


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def local_server(tmp_path: Path):
    build_dir = tmp_path / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    images_dir = build_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # Copy static assets
    static_dir = Path(__file__).parent.parent / "src" / "confwall" / "static"
    for f in static_dir.glob("*"):
        (build_dir / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")

    # Create dummy image
    (images_dir / "dummy.jpg").write_bytes(b"dummy")

    # Write slides.json with all features populated
    from datetime import datetime, timedelta, timezone
    near_future_iso = (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")

    slides_data = {
        "slide_seconds": 1,
        "slides": [
            {
                "id": "mlsys-2027",
                "acronym": "MLSys",
                "full_name": "Conference on Machine Learning and Systems",
                "year": 2027,
                "conference_url": "https://mlsys.org",
                "deadline_utc": near_future_iso,
                "deadline_text": "In 10 Days · 23:59 AoE",
                "deadline_comment": "Round 2",
                "abstract_deadline_text": "In 3 Days · 23:59 AoE",
                "publisher_tag": "ACM",
                "format_tag": "In-Person",
                "rank_core": "A*",
                "rank_ccf": "A",
                "location_display": "Austin, USA",
                "city": "Austin",
                "country": "USA",
                "primary_focus": "Machine Learning",
                "photo_path": "images/dummy.jpg",
                "photo_credit": "Photo by Jane Smith on Pexels",
                "photo_source_url": "https://pexels.com",
            },
            {
                "id": "osdi-2026",
                "acronym": "OSDI",
                "full_name": "USENIX Symposium on Operating Systems Design and Implementation",
                "year": 2026,
                "conference_url": "https://usenix.org",
                "deadline_utc": "2026-11-05T23:59:00Z",
                "deadline_text": "November 5, 2026 · 23:59 UTC-8",
                "deadline_comment": None,
                "abstract_deadline_text": "October 20, 2026 · 23:59 UTC-8",
                "publisher_tag": "USENIX",
                "format_tag": "Hybrid",
                "rank_core": "A*",
                "rank_ccf": "A",
                "location_display": "Carlsbad, USA",
                "city": "Carlsbad",
                "country": "USA",
                "primary_focus": "Software Systems",
                "photo_path": "images/dummy.jpg",
                "photo_credit": "Photo by John Doe",
                "photo_source_url": None,
            },
        ],
    }

    (build_dir / "slides.json").write_text(json.dumps(slides_data), encoding="utf-8")

    port = find_free_port()

    class CustomHandler(ConfwallRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(build_dir), **kwargs)

    server = ThreadingHTTPServer(("127.0.0.1", port), CustomHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield f"http://127.0.0.1:{port}", build_dir

    server.shutdown()
    server.server_close()


def test_browser_slideshow(local_server):
    url, _build_dir = local_server

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # 1. Load slideshow with ?seed=123 for deterministic shuffle
        page.goto(f"{url}/index.html?seed=123")

        # 2. Check title & caption text visible
        page.wait_for_selector("#slide-acronym")
        acronym_text = page.text_content("#slide-acronym")
        assert acronym_text in ("MLSys", "OSDI")

        # Required header and caption text
        assert page.is_visible(".site-header-badge")
        assert "Upcoming Conferences" in page.text_content(".site-header-badge")
        assert page.is_visible("#slide-location")
        assert page.is_visible("#slide-deadline")
        assert page.is_visible("#photo-credit")

        # Assert new feature UI elements are visible and rendered correctly
        assert page.is_visible("#slide-publisher")
        assert page.text_content("#slide-publisher") in ("ACM", "USENIX")

        assert page.is_visible("#slide-format")
        format_text = page.text_content("#slide-format")
        assert "In-Person" in format_text or "Hybrid" in format_text or "Remote" in format_text

        assert page.is_visible("#slide-ranks")
        assert "CORE A*" in page.text_content("#slide-ranks")

        assert page.is_visible("#slide-abstract-box")
        assert "Abstract due:" in page.text_content("#slide-abstract-box")

        # Check popping countdown visibility if current slide is within 30 days
        if page.is_visible("#slide-countdown"):
          assert "remaining!" in page.text_content("#slide-countdown")

        # 3. Check right arrow changes slide
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(200)

        # 4. Check space pauses advancement
        page.keyboard.press("Space")

        # Assert no console errors
        assert len(console_errors) == 0

        browser.close()


def test_browser_empty_state(local_server):
    url, build_dir = local_server
    # Overwrite slides.json with empty slides
    (build_dir / "slides.json").write_text(json.dumps({"slide_seconds": 15, "slides": []}), encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{url}/index.html")

        page.wait_for_selector("#empty-state")
        assert page.is_visible("#empty-state")
        assert "No selected conference submission deadlines" in page.text_content("#empty-state")

        browser.close()
