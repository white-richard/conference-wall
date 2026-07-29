import json
from datetime import UTC, datetime
from pathlib import Path

from confwall.models import Slide
from confwall.site_builder import build_site_atomically


def test_build_site_atomically(tmp_path: Path):
    output_dir = tmp_path / "build"
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    (images_dir / "test.jpg").write_bytes(b"jpg_data")

    slides = [
        Slide(
            id="mlsys-2027",
            acronym="MLSys",
            full_name="Conference on Machine Learning and Systems (München Edition)",
            year=2027,
            conference_url="https://mlsys.org",
            deadline_utc=datetime(2026, 10, 30, 23, 59, tzinfo=UTC),
            deadline_text="October 30, 2026 · 23:59 AoE",
            deadline_comment="Round 2",
            location_display="München, Germany",
            city="München",
            country="Germany",
            primary_focus="Machine Learning",
            photo_path="images/test.jpg",
            photo_credit="Photo by Max Mustermann",
            photo_source_url="https://example.com/photo",
        )
    ]

    build_site_atomically(output_dir, slides, images_dir, slide_seconds=15)

    assert (output_dir / "index.html").exists()
    assert (output_dir / "app.js").exists()
    assert (output_dir / "style.css").exists()
    assert (output_dir / "slides.json").exists()
    assert (output_dir / "images" / "test.jpg").exists()

    data = json.loads((output_dir / "slides.json").read_text(encoding="utf-8"))
    assert data["slide_seconds"] == 15
    assert len(data["slides"]) == 1
    assert data["slides"][0]["acronym"] == "MLSys"
    assert data["slides"][0]["city"] == "München"


def test_build_site_empty_slides(tmp_path: Path):
    output_dir = tmp_path / "build"
    images_dir = tmp_path / "images"
    images_dir.mkdir()

    build_site_atomically(output_dir, [], images_dir, slide_seconds=10)

    data = json.loads((output_dir / "slides.json").read_text(encoding="utf-8"))
    assert data["slides"] == []
