"""Integration tests for confwall refresh workflow."""

import json
from pathlib import Path

from confwall.cli import run_refresh


def test_integration_refresh_workflow(tmp_path: Path, monkeypatch):
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        """
window_months: 4
slide_seconds: 15
venues:
  mlsys:
    aliases: [MLSys]
    primary_focus: Machine Learning
  osdi:
    aliases: [OSDI]
    primary_focus: Software Systems
  chi:
    aliases: [CHI]
    primary_focus: HCI
""",
        encoding="utf-8",
    )

    fixture_snapshot_dir = Path(__file__).parent / "fixtures" / "ccf_snapshot"
    output_dir = tmp_path / "build"

    # Mock CCFConferenceSource to use our fixture directory
    from confwall.conference_source import CCFConferenceSource

    def mock_load_editions(self, config, snapshot_zip_bytes=None):
        return self.fetch_records_from_directory(fixture_snapshot_dir, config)

    monkeypatch.setattr(CCFConferenceSource, "load_editions", mock_load_editions)

    # 1. First refresh with --now 2026-07-24T12:00:00Z
    now_str = "2026-07-24T12:00:00Z"
    res1 = run_refresh(
        config_path=config_file,
        output_dir=output_dir,
        now_arg=now_str,
        verbose=True,
    )
    assert res1 == 0

    # Assert build structure
    assert (output_dir / "slides.json").exists()
    assert (output_dir / "images" / "fallback-city.jpg").exists()

    slides_data = json.loads((output_dir / "slides.json").read_text(encoding="utf-8"))
    slides = slides_data["slides"]
    assert len(slides) > 0

    # Verify slide details
    acronyms = {s["acronym"] for s in slides}
    assert "MLSys" in acronyms or "OSDI" in acronyms or "CHI" in acronyms
    assert "UNCONFIGURED_VENUE" not in acronyms

    for s in slides:
        assert "acronym" in s
        assert "full_name" in s
        assert "year" in s
        assert "deadline_text" in s
        assert "location_display" in s
        assert "primary_focus" in s
        assert "photo_path" in s
        assert "photo_credit" in s

    # 2. Second refresh should succeed and reuse cached data
    res2 = run_refresh(
        config_path=config_file,
        output_dir=output_dir,
        now_arg=now_str,
        verbose=False,
    )
    assert res2 == 0

    # 3. Simulate a failed third refresh and verify prior build remains intact
    def failing_load_editions(self, config, snapshot_zip_bytes=None):
        raise RuntimeError("Upstream snapshot download failed")

    monkeypatch.setattr(CCFConferenceSource, "load_editions", failing_load_editions)

    res3 = run_refresh(
        config_path=config_file,
        output_dir=output_dir,
        now_arg=now_str,
        verbose=False,
    )
    assert res3 == 1
    # Prior build directory must still exist and contain slides.json
    assert (output_dir / "slides.json").exists()
    data_after_fail = json.loads((output_dir / "slides.json").read_text(encoding="utf-8"))
    assert len(data_after_fail["slides"]) == len(slides)
