"""Tests for photo caching, overrides, fallbacks, search, and secret protection."""

import io
import json
import logging
from pathlib import Path

import pytest
from PIL import Image

from confwall.config import PhotoOverride
from confwall.http_client import HttpClient
from confwall.locations import parse_location
from confwall.models import PhotoManifestEntry
from confwall.photos import PhotoManager


def create_valid_jpeg_bytes(width: int = 1920, height: int = 1080) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color="blue")
    img.save(buf, "JPEG")
    return buf.getvalue()


def test_photo_cache_hit_and_override(tmp_path: Path):
    manifest_path = tmp_path / "data" / "photo_manifest.json"
    images_dir = tmp_path / "build" / "images"
    fallback_path = tmp_path / "assets" / "fallback-city.jpg"
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_path.write_bytes(create_valid_jpeg_bytes())

    mgr = PhotoManager(
        manifest_path=manifest_path,
        images_dir=images_dir,
        fallback_path=fallback_path,
    )

    # 1. Missing API key uses fallback
    loc = parse_location("Vienna, Austria")
    rel_path, credit, _source_url, _is_new = mgr.resolve_photo_for_location(loc)
    assert rel_path == "images/fallback-city.jpg"
    assert credit == "Fallback Image"

    # 2. Local override file wins
    override_img = tmp_path / "custom_vienna.jpg"
    override_img.write_bytes(create_valid_jpeg_bytes())

    overrides = {
        "vienna|austria": PhotoOverride(file=str(override_img), credit="Custom Photo")
    }

    rel_path_ovr, credit_ovr, _, _ = mgr.resolve_photo_for_location(loc, overrides=overrides)
    assert "override" in rel_path_ovr
    assert credit_ovr == "Custom Photo"


def test_photo_search_pexels(tmp_path: Path, monkeypatch):
    manifest_path = tmp_path / "data" / "photo_manifest.json"
    images_dir = tmp_path / "build" / "images"
    fallback_path = tmp_path / "assets" / "fallback-city.jpg"
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_path.write_bytes(create_valid_jpeg_bytes())

    monkeypatch.setenv("PEXELS_API_KEY", "fake_key")

    http_client = HttpClient()

    def mock_get_json(self, url, headers=None, params=None):
        if "photos/123" in url:
            return {
                "id": 123,
                "photographer": "Jane Smith",
                "photographer_url": "https://pexels.com/@jane",
                "url": "https://pexels.com/photo/123",
                "width": 2000,
                "height": 1000,
                "src": {"landscape": "https://images.pexels.com/123.jpg"},
            }
        return {
            "photos": [
                {
                    "id": 456,
                    "photographer": "John Doe",
                    "photographer_url": "https://pexels.com/@john",
                    "url": "https://pexels.com/photo/456",
                    "width": 2000,
                    "height": 1000,
                    "alt": "Austin Texas USA aerial skyline",
                    "src": {"landscape": "https://images.pexels.com/456.jpg"},
                }
            ]
        }

    def mock_get_bytes(self, url, headers=None):
        return create_valid_jpeg_bytes()

    monkeypatch.setattr(HttpClient, "get_json", mock_get_json)
    monkeypatch.setattr(HttpClient, "get_bytes", mock_get_bytes)

    mgr = PhotoManager(
        manifest_path=manifest_path,
        images_dir=images_dir,
        fallback_path=fallback_path,
        http_client=http_client,
    )

    # Resolve photo via search
    loc = parse_location("Austin, TX, USA")
    rel_path, credit, _source_url, is_new = mgr.resolve_photo_for_location(loc)
    assert "austin-usa-456.jpg" in rel_path
    assert "John Doe" in credit
    assert is_new is True

    # Manifest saved
    assert manifest_path.exists()
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "austin|usa" in manifest_data

    # Test override with pexels_id
    loc_ovr = parse_location("Austin, TX, USA")
    overrides = {"austin|usa": PhotoOverride(pexels_id=123)}
    rel_path_id, credit_id, _, _ = mgr.resolve_photo_for_location(loc_ovr, overrides=overrides)
    assert "123" in rel_path_id
    assert "Jane Smith" in credit_id


def test_photo_redownload_and_corrupt_file(tmp_path: Path, monkeypatch):
    manifest_path = tmp_path / "data" / "photo_manifest.json"
    images_dir = tmp_path / "build" / "images"
    fallback_path = tmp_path / "assets" / "fallback-city.jpg"
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_path.write_bytes(create_valid_jpeg_bytes())

    # Pre-populate manifest with a record whose local file is missing
    entry = PhotoManifestEntry(
        location_key="paris|france",
        provider="pexels",
        photo_id=999,
        query="Paris France",
        photographer="Pierre",
        photographer_url="",
        source_url="https://images.pexels.com/999.jpg",
        local_file="images/paris-france-999.jpg",
        width=2000,
        height=1000,
        selected_at="2026-07-24T00:00:00Z",
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({"paris|france": entry.to_dict()}), encoding="utf-8")

    http_client = HttpClient()

    def mock_get_bytes(self, url, headers=None):
        return create_valid_jpeg_bytes()

    monkeypatch.setattr(HttpClient, "get_bytes", mock_get_bytes)

    mgr = PhotoManager(
        manifest_path=manifest_path,
        images_dir=images_dir,
        fallback_path=fallback_path,
        http_client=http_client,
    )

    loc = parse_location("Paris, France")
    rel_path, _credit, _, is_new = mgr.resolve_photo_for_location(loc)
    assert rel_path == "images/paris-france-999.jpg"
    assert is_new is True  # Redownloaded


def test_secret_never_in_logs_or_manifest(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    manifest_path = tmp_path / "data" / "photo_manifest.json"
    images_dir = tmp_path / "build" / "images"
    fallback_path = tmp_path / "assets" / "fallback-city.jpg"
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_path.write_bytes(create_valid_jpeg_bytes())

    secret_key = "PEXELS_SECRET_KEY_12345_DO_NOT_LOG"
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("PEXELS_API_KEY", secret_key)

    mgr = PhotoManager(
        manifest_path=manifest_path,
        images_dir=images_dir,
        fallback_path=fallback_path,
    )

    with caplog.at_level(logging.DEBUG):
        mgr.resolve_photo_for_location(parse_location("Austin, TX, USA"))

    # Assert secret never appears in logs
    assert secret_key not in caplog.text

    # Assert secret never appears in manifest file
    if manifest_path.exists():
        assert secret_key not in manifest_path.read_text(encoding="utf-8")

    monkeypatch.undo()
