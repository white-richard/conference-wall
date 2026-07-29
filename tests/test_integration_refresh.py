import json
from pathlib import Path

from confwall.cli import run_refresh


def test_integration_refresh_workflow(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        """
window_months: 4
slide_seconds: 15
auto_discover: false
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
        dotenv_path=None,
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
        dotenv_path=None,
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
        dotenv_path=None,
    )
    assert res3 == 1
    # Prior build directory must still exist and contain slides.json
    assert (output_dir / "slides.json").exists()
    data_after_fail = json.loads((output_dir / "slides.json").read_text(encoding="utf-8"))
    assert len(data_after_fail["slides"]) == len(slides)


def test_refresh_workflow_for_all_new_groups(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        """
window_months: 4
auto_discover: true
venues:
  ismb:
    aliases: [ISMB]
    primary_focus: Bioinformatics
  recomb:
    aliases: [RECOMB]
    primary_focus: Computational Biology
  cgo:
    aliases: [CGO, IEEE/ACM CGO]
    primary_focus: Optimization
  cosyne:
    aliases: [COSYNE]
    primary_focus: Computational Neuroscience
""",
        encoding="utf-8",
    )

    from confwall.conference_source import CCFConferenceSource
    from confwall.models import ConferenceEdition

    mock_editions = [
        ConferenceEdition(
            venue_id="ismb",
            acronym="ISMB",
            full_name="Intelligent Systems for Molecular Biology",
            year=2026,
            link="https://ismb.org",
            timeline=({"deadline": "2026-09-01 23:59:59"},),
            timezone="UTC",
            place="Boston, MA, USA",
            sub="BIO",
        ),
        ConferenceEdition(
            venue_id="recomb",
            acronym="RECOMB",
            full_name="Research in Computational Molecular Biology",
            year=2026,
            link="https://recomb.org",
            timeline=({"deadline": "2026-09-10 23:59:59"},),
            timezone="UTC",
            place="Thessaloniki, Greece",
            sub="CB",
        ),
        ConferenceEdition(
            venue_id="cgo",
            acronym="IEEE/ACM CGO",
            full_name="Code Generation and Optimization",
            year=2027,
            link="https://cgo.org",
            timeline=({"deadline": "2026-09-11 23:59:59"},),
            timezone="UTC",
            place="Salt Lake City, UT, USA",
            sub="OPT",
        ),
        ConferenceEdition(
            venue_id="cosyne",
            acronym="COSYNE",
            full_name="Computational and Systems Neuroscience",
            year=2027,
            link="https://cosyne.org",
            timeline=({"deadline": "2026-10-01 23:59:59"},),
            timezone="UTC",
            place="Denver, CO, USA",
            sub="CNS",
        ),
    ]

    def mock_load_editions(self, config, snapshot_zip_bytes=None):
        return mock_editions, len(mock_editions)

    monkeypatch.setattr(CCFConferenceSource, "load_editions", mock_load_editions)

    output_dir = tmp_path / "build"
    res = run_refresh(
        config_path=config_file,
        output_dir=output_dir,
        now_arg="2026-07-28T12:00:00Z",
        verbose=True,
        dotenv_path=None,
    )
    assert res == 0

    slides_data = json.loads((output_dir / "slides.json").read_text(encoding="utf-8"))
    slides = slides_data["slides"]
    assert len(slides) == 4

    focuses = {s["primary_focus"] for s in slides}
    assert "Bioinformatics" in focuses
    assert "Computational Biology" in focuses
    assert "Optimization" in focuses
    assert "Computational Neuroscience" in focuses

