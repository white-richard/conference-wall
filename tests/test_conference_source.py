import io
import zipfile
from pathlib import Path

import pytest

from confwall.conference_source import CCFConferenceSource
from confwall.config import Config, VenueConfig


@pytest.fixture
def mock_config() -> Config:
    return Config(
        window_months=4,
        venues={
            "mlsys": VenueConfig(primary_focus="Machine Learning", aliases=("MLSys",)),
            "osdi": VenueConfig(primary_focus="Software Systems", aliases=("OSDI",)),
            "chi": VenueConfig(primary_focus="HCI", aliases=("CHI",)),
        },
        alias_map={"mlsys": "mlsys", "osdi": "osdi", "chi": "chi"},
    )


def test_conference_source_load_from_directory(mock_config: Config):
    fixture_dir = Path(__file__).parent / "fixtures" / "ccf_snapshot"
    source = CCFConferenceSource()
    editions, total_records = source.fetch_records_from_directory(fixture_dir, mock_config)

    assert total_records == 4
    assert len(editions) == 3

    venue_ids = {ed.venue_id for ed in editions}
    assert venue_ids == {"mlsys", "osdi", "chi"}


def test_conference_source_load_from_zip(mock_config: Config):
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
        # Unmatched file
        z.writestr(
            "ccf-deadlines-main/conference/OTHER/unknown.yml",
            """
- title: UNKNOWN
  confs:
    - year: 2026
""",
        )

    source = CCFConferenceSource()
    editions, count = source.load_editions(mock_config, snapshot_zip_bytes=buf.getvalue())
    assert count == 2
    assert len(editions) == 1
    assert editions[0].venue_id == "osdi"
