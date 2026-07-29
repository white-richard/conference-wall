"""Tests for new slideshow features: publisher tags, format pills, abstract deadlines, keywords, rankings, and countdowns."""

from datetime import datetime, timezone

from confwall.config import Config, VenueConfig
from confwall.deadlines import (
    detect_format,
    detect_publisher,
    select_next_deadline,
)
from confwall.models import ConferenceEdition, Slide
from confwall.site_builder import slide_to_dict


def test_detect_publisher():
    assert detect_publisher("CHI", "ACM CHI Conference", "chi") == "ACM"
    assert detect_publisher("BIBM", "IEEE BIBM", "bibm") == "IEEE"
    assert detect_publisher("CGO", "IEEE/ACM CGO", "cgo") == "IEEE / ACM"
    assert detect_publisher("OSDI", "USENIX OSDI", "osdi") == "USENIX"
    assert detect_publisher("MLSys", "Conference on Machine Learning and Systems", "mlsys") == "Other"


def test_detect_format():
    assert detect_format("Austin, TX, USA") == "In-Person"
    assert detect_format("Virtual") == "Remote"
    assert detect_format("Online") == "Remote"
    assert detect_format("Málaga, Spain (hybrid)") == "Hybrid"
    assert detect_format("Bruges, Belgium and Online") == "Hybrid"
    assert detect_format("TBD") == "TBD"


def test_detect_format_remote_without_venue():
    """Filler words next to a remote keyword must not read as a physical venue."""
    assert detect_format("Virtual Event") == "Remote"
    assert detect_format("Online Event") == "Remote"
    assert detect_format("Fully Virtual") == "Remote"
    assert detect_format("Virtual conference") == "Remote"
    assert detect_format("Online (Zoom)") == "Remote"
    assert detect_format("Remote Only") == "Remote"


def test_detect_format_ignores_substring_matches():
    """Real cities that merely contain a remote keyword stay In-Person."""
    assert detect_format("Cyberjaya, Malaysia") == "In-Person"
    assert detect_format("Cybersecurity Center, Tel Aviv") == "In-Person"
    assert detect_format("Onlineville, USA") == "In-Person"


def test_abstract_deadline_selection():
    now = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    timeline = (
        {
            "deadline": "2026-08-01 23:59:59",
            "comment": "Abstract Due",
        },
        {
            "deadline": "2026-08-15 23:59:59",
            "comment": "Full Paper Submission",
        },
    )
    d_info = select_next_deadline(timeline, "UTC", now, display_tz_target="UTC")
    assert d_info is not None
    assert "August 15, 2026" in d_info.deadline_text
    assert d_info.abstract_deadline_text is not None
    assert "August 1, 2026" in d_info.abstract_deadline_text


def test_abstract_deadline_inline_key():
    now = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    timeline = (
        {
            "abstract_deadline": "2026-08-01 23:59:59",
            "deadline": "2026-08-15 23:59:59",
        },
    )
    d_info = select_next_deadline(timeline, "UTC", now, display_tz_target="UTC")
    assert d_info is not None
    assert d_info.abstract_deadline_text is not None
    assert "August 1, 2026" in d_info.abstract_deadline_text


def test_slide_serialization():
    dt = datetime(2026, 10, 15, 23, 59, tzinfo=timezone.utc)
    slide = Slide(
        id="osdi-2026",
        acronym="OSDI",
        full_name="USENIX Symposium on Operating Systems Design and Implementation",
        year=2026,
        conference_url="https://usenix.org/osdi26",
        deadline_utc=dt,
        deadline_text="October 15, 2026 · 23:59 PST",
        deadline_comment="Round 1",
        location_display="Carlsbad, CA, USA",
        city="Carlsbad",
        country="USA",
        primary_focus="Software Systems",
        photo_path="images/carlsbad.jpg",
        photo_credit="Pexels / Photographer",
        photo_source_url="https://pexels.com",
        publisher_tag="USENIX",
        format_tag="In-Person",
        abstract_deadline_text="October 1, 2026 · 23:59 PST",
        rank_core="A*",
        rank_ccf="A",
    )
    d = slide_to_dict(slide)
    assert d["publisher_tag"] == "USENIX"
    assert d["format_tag"] == "In-Person"
    assert d["abstract_deadline_text"] == "October 1, 2026 · 23:59 PST"
    assert d["rank_core"] == "A*"
    assert d["rank_ccf"] == "A"
