import io
import runpy
import shutil
import zipfile
from pathlib import Path

import pytest

from confwall.cli import run_refresh
from confwall.conference_source import CCFConferenceSource
from confwall.config import PhotoOverride
from confwall.deadlines import parse_deadline_datetime, select_next_deadline
from confwall.http_client import HttpClient
from confwall.locations import parse_location
from confwall.models import ConferenceEdition, PhotoManifestEntry
from confwall.photos import PhotoManager
from confwall.site_builder import build_site_atomically


def test_main_execution_entrypoint(monkeypatch):
    monkeypatch.setattr("sys.argv", ["confwall", "--help"])
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("confwall.__main__", run_name="__main__")
    assert exc_info.value.code == 0


def test_deadlines_edge_cases():
    # Naive dateutil fallback
    res = parse_deadline_datetime("October 30, 2026 23:59:00", tz_override="UTC")
    assert res is not None

    # Invalid timezone string
    res_bad_tz = parse_deadline_datetime("2026-10-30 23:59:00", tz_override="INVALID_TZ")
    assert res_bad_tz is not None

    # Empty timeline
    from datetime import datetime, timezone
    now = datetime(2026, 7, 24, tzinfo=timezone.utc)
    assert select_next_deadline([], "UTC", now) is None
    assert select_next_deadline([None, "invalid"], "UTC", now) is None


def test_conference_source_stem_matching_and_invalid_confs(mock_config):
    yaml_content = """
- title: ""
  description: USENIX OSDI
  confs:
    - year: invalid_year
    - year: 2026
      timeline: invalid_timeline
      place: Carlsbad, CA, USA
- title: OSDI
  confs: invalid_confs_type
- not_a_dict_item
"""
    source = CCFConferenceSource()
    editions, count = source._parse_yaml_content(yaml_content, mock_config, source_name="osdi.yml")
    assert count == 3
    assert len(editions) == 1
    assert editions[0].venue_id == "osdi"


def test_conference_source_zip_download(monkeypatch, mock_config):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "ccf-deadlines-main/conference/SYS/osdi.yml",
            """
- title: OSDI
  description: USENIX Symposium on Operating Systems Design and Implementation
  confs:
    - year: 2026
      timeline:
        - deadline: '2026-08-15 23:59:59'
      place: Carlsbad, CA, USA
""",
        )

    def mock_get_bytes(self, url, headers=None):
        return buf.getvalue()

    monkeypatch.setattr(HttpClient, "get_bytes", mock_get_bytes)

    source = CCFConferenceSource()
    editions, count = source.load_editions(mock_config)
    assert count == 1
    assert len(editions) == 1


def test_cli_refresh_skipped_branches(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text(
        """
window_months: 4
venues:
  osdi:
    aliases: [OSDI]
    primary_focus: Software Systems
""",
        encoding="utf-8",
    )

    editions = [
        # Edition with no future deadline
        ConferenceEdition(
            venue_id="osdi",
            acronym="OSDI",
            full_name="OSDI",
            year=2020,
            link="",
            timeline=({"deadline": "2020-01-01 00:00:00"},),
            timezone="UTC",
            place="Las Vegas, NV, USA",
        ),
        # Edition outside 4 months
        ConferenceEdition(
            venue_id="osdi",
            acronym="OSDI",
            full_name="OSDI",
            year=2027,
            link="",
            timeline=({"deadline": "2027-12-01 00:00:00"},),
            timezone="UTC",
            place="Las Vegas, NV, USA",
        ),
        # Duplicate edition
        ConferenceEdition(
            venue_id="osdi",
            acronym="OSDI",
            full_name="OSDI",
            year=2026,
            link="",
            timeline=({"deadline": "2026-08-01 00:00:00"},),
            timezone="UTC",
            place="Las Vegas, NV, USA",
        ),
        ConferenceEdition(
            venue_id="osdi",
            acronym="OSDI",
            full_name="OSDI",
            year=2026,
            link="",
            timeline=({"deadline": "2026-08-01 00:00:00"},),
            timezone="UTC",
            place="Las Vegas, NV, USA",
        ),
    ]

    def mock_load_editions(self, config, snapshot_zip_bytes=None):
        return editions, len(editions)

    monkeypatch.setattr(CCFConferenceSource, "load_editions", mock_load_editions)

    output_dir = tmp_path / "build"
    res = run_refresh(
        config_path=cfg_file,
        output_dir=output_dir,
        now_arg="2026-07-24T12:00:00Z",
        verbose=True,
    )
    assert res == 0


def test_cli_refresh_additional_errors(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "corrupt_config.yml"
    cfg_file.write_text("invalid: [yaml: {{{", encoding="utf-8")

    # Corrupt config load failure
    assert run_refresh(config_path=cfg_file, output_dir=tmp_path / "build") == 1

    # Site builder failure
    valid_cfg = tmp_path / "config.yml"
    valid_cfg.write_text("venues: {}\n", encoding="utf-8")

    def failing_build(*args, **kwargs):
        raise RuntimeError("Build error")

    monkeypatch.setattr("confwall.cli.build_site_atomically", failing_build)
    assert run_refresh(config_path=valid_cfg, output_dir=tmp_path / "build") == 1


def test_photos_more_branches(tmp_path: Path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    images_dir = tmp_path / "images"
    fallback_path = tmp_path / "assets" / "fallback-city.jpg"
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_path.write_bytes(b"fallback")

    monkeypatch.setenv("PEXELS_API_KEY", "fake_key")

    http_client = HttpClient()

    # Pexels candidate download invalid bytes
    def mock_get_json(self, url, headers=None, params=None):
        return {
            "photos": [
                {
                    "id": 888,
                    "photographer": "Bad Image",
                    "width": 2000,
                    "height": 1000,
                    "alt": "City skyline",
                    "src": {"landscape": "https://images.pexels.com/bad.jpg"},
                }
            ]
        }

    def mock_get_bytes(self, url, headers=None):
        return b"invalid bytes that pillow cannot decode"

    monkeypatch.setattr(HttpClient, "get_json", mock_get_json)
    monkeypatch.setattr(HttpClient, "get_bytes", mock_get_bytes)

    mgr = PhotoManager(manifest_path, images_dir, fallback_path, http_client=http_client)
    loc = parse_location("Berlin, Germany")
    rel_path, _credit, _, _ = mgr.resolve_photo_for_location(loc)
    # Should fall back because downloaded bytes invalid
    assert rel_path == "images/fallback-city.jpg"

    # Override file missing
    loc_ovr = parse_location("Berlin, Germany")
    overrides = {"berlin|germany": PhotoOverride(file="nonexistent_override.jpg")}
    rel_path_ovr, _, _, _ = mgr.resolve_photo_for_location(loc_ovr, overrides=overrides)
    assert rel_path_ovr == "images/fallback-city.jpg"

    # Pexels override ID exception
    def failing_get_json(self, url, headers=None, params=None):
        raise RuntimeError("API error")

    monkeypatch.setattr(HttpClient, "get_json", failing_get_json)
    ovr_id = {"berlin|germany": PhotoOverride(pexels_id=123)}
    rel_path_id, _, _, _ = mgr.resolve_photo_for_location(loc_ovr, overrides=ovr_id)
    assert rel_path_id == "images/fallback-city.jpg"


def test_site_builder_error_handling(tmp_path: Path, monkeypatch):
    output_dir = tmp_path / "build"
    output_dir.mkdir()
    (output_dir / "existing.txt").write_text("old")

    images_dir = tmp_path / "images"
    images_dir.mkdir()

    def failing_copytree(src, dst):
        raise RuntimeError("Copy failed")

    monkeypatch.setattr(shutil, "copytree", failing_copytree)

    with pytest.raises(RuntimeError):
        build_site_atomically(output_dir, [], images_dir)


def test_cli_refresh_error_paths(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text("venues: {}\n", encoding="utf-8")

    def failing_load_editions(self, config, snapshot_zip_bytes=None):
        raise RuntimeError("Network error")

    monkeypatch.setattr(CCFConferenceSource, "load_editions", failing_load_editions)

    res = run_refresh(config_path=cfg_file, output_dir=tmp_path / "build")
    assert res == 1


def test_photos_validation_and_manifest_errors(tmp_path: Path, monkeypatch):
    manifest_path = tmp_path / "corrupt_manifest.json"
    manifest_path.write_text("invalid json {{{", encoding="utf-8")
    images_dir = tmp_path / "images"
    fallback_path = tmp_path / "assets" / "fallback-city.jpg"
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_path.write_bytes(b"fallback")

    mgr = PhotoManager(manifest_path, images_dir, fallback_path)
    assert mgr.manifest == {}

    # Validation invalid image bytes
    assert mgr._validate_image_bytes(b"not an image") is False

    # Validation invalid image file
    corrupt_file = tmp_path / "corrupt.jpg"
    corrupt_file.write_bytes(b"not an image")
    assert mgr._validate_image_file(corrupt_file) is False

    # Redownload manifest photo failure
    entry = PhotoManifestEntry(
        location_key="rome|italy",
        provider="pexels",
        photo_id=777,
        query="",
        photographer="",
        photographer_url="",
        source_url="https://invalid.url/img.jpg",
        local_file="images/rome-777.jpg",
        width=1000,
        height=1000,
        selected_at="",
    )

    def failing_get_bytes(self, url, headers=None):
        raise RuntimeError("Download error")

    monkeypatch.setattr(HttpClient, "get_bytes", failing_get_bytes)

    assert mgr._redownload_manifest_photo(entry) is False
