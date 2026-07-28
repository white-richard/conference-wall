"""Tests for config loading, dotenv parsing, and alias resolution."""

import os
from pathlib import Path

import pytest

from confwall.config import (
    Config,
    load_config,
    load_dotenv,
    load_photo_overrides,
)


def test_load_dotenv(tmp_path: Path, monkeypatch):
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text(
        """
# Comment line
PEXELS_API_KEY="test_key_from_env_file"
OTHER_SETTING=12345
""",
        encoding="utf-8",
    )
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("OTHER_SETTING", raising=False)

    load_dotenv(dotenv_file)

    assert os.environ.get("PEXELS_API_KEY") == "test_key_from_env_file"
    assert os.environ.get("OTHER_SETTING") == "12345"


def test_load_config_file_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nonexistent.yml")


def test_load_config_valid(tmp_path: Path):
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text(
        """
window_months: 5
slide_seconds: 20
venues:
  osdi:
    aliases: [OSDI, USENIX OSDI]
    primary_focus: Software Systems
  chi:
    aliases: [CHI]
    primary_focus: HCI
location_overrides:
  "Las Vegas, NV, USA":
    city: Las Vegas
    country: USA
    display: Las Vegas, Nevada, USA
""",
        encoding="utf-8",
    )

    cfg = load_config(cfg_file)
    assert cfg.window_months == 5
    assert cfg.slide_seconds == 20
    assert "osdi" in cfg.venues
    assert cfg.venues["osdi"].primary_focus == "Software Systems"

    # Alias matching
    assert cfg.get_venue_id_for_alias("OSDI") == "osdi"
    assert cfg.get_venue_id_for_alias("usenix osdi") == "osdi"
    assert cfg.get_venue_id_for_alias("chi") == "chi"
    assert cfg.get_venue_id_for_alias("UNKNOWN") is None

    # Location override
    assert "Las Vegas, NV, USA" in cfg.location_overrides
    ovr = cfg.location_overrides["Las Vegas, NV, USA"]
    assert ovr.city == "Las Vegas"
    assert ovr.display == "Las Vegas, Nevada, USA"


def test_load_photo_overrides(tmp_path: Path):
    photo_file = tmp_path / "photo_overrides.yml"
    photo_file.write_text(
        """
photos:
  "las vegas|usa":
    pexels_id: 12345678
  "hamburg|germany":
    file: local_photos/hamburg.jpg
    credit: "Photo by the lab"
""",
        encoding="utf-8",
    )

    overrides = load_photo_overrides(photo_file)
    assert "las vegas|usa" in overrides
    assert overrides["las vegas|usa"].pexels_id == 12345678
    assert overrides["hamburg|germany"].file == "local_photos/hamburg.jpg"
    assert overrides["hamburg|germany"].credit == "Photo by the lab"

    # Non-existent file
    assert load_photo_overrides(tmp_path / "missing.yml") == {}


def test_ccf_sub_map_new_groups():
    cfg = Config(auto_discover=True)
    assert cfg.get_primary_focus("unknown_venue", sub_category="BIO") == "Bioinformatics"
    assert cfg.get_primary_focus("unknown_venue", sub_category="BIOINFORMATICS") == "Bioinformatics"
    assert cfg.get_primary_focus("unknown_venue", sub_category="CB") == "Computational Biology"
    assert cfg.get_primary_focus("unknown_venue", sub_category="COMPBIO") == "Computational Biology"
    assert cfg.get_primary_focus("unknown_venue", sub_category="COMPUTATIONAL BIOLOGY") == "Computational Biology"
    assert cfg.get_primary_focus("unknown_venue", sub_category="BCB") == "Computational Biology"
    assert cfg.get_primary_focus("unknown_venue", sub_category="OPT") == "Optimization"
    assert cfg.get_primary_focus("unknown_venue", sub_category="OPTIMIZATION") == "Optimization"
    assert cfg.get_primary_focus("unknown_venue", sub_category="CNS") == "Computational Neuroscience"
    assert cfg.get_primary_focus("unknown_venue", sub_category="NEURO") == "Computational Neuroscience"
    assert cfg.get_primary_focus("unknown_venue", sub_category="COMPNEURO") == "Computational Neuroscience"
    assert cfg.get_primary_focus("unknown_venue", sub_category="COMPUTATIONAL NEUROSCIENCE") == "Computational Neuroscience"


def test_root_config_file():
    root_cfg_path = Path(__file__).parent.parent / "config.yml"
    cfg = load_config(root_cfg_path)
    assert "ismb" in cfg.venues
    assert cfg.venues["ismb"].primary_focus == "Bioinformatics"
    assert "recomb" in cfg.venues
    assert cfg.venues["recomb"].primary_focus == "Computational Biology"
    assert "ipco" in cfg.venues
    assert cfg.venues["ipco"].primary_focus == "Optimization"
    assert "cosyne" in cfg.venues
    assert cfg.venues["cosyne"].primary_focus == "Computational Neuroscience"

