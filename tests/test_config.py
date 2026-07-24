"""Tests for config loading, dotenv parsing, and alias resolution."""

import os
from pathlib import Path

import pytest

from confwall.config import (
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
