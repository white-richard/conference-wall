"""Configuration loader and models for confwall."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class VenueConfig:
    primary_focus: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class LocationOverride:
    city: str
    country: str
    display: str


@dataclass(frozen=True)
class PhotoOverride:
    pexels_id: int | str | None = None
    file: str | None = None
    credit: str | None = None


@dataclass
class Config:
    window_months: int = 4
    slide_seconds: int = 15
    display_timezone: str = "PST"
    venues: dict[str, VenueConfig] = field(default_factory=dict)
    location_overrides: dict[str, LocationOverride] = field(default_factory=dict)
    alias_map: dict[str, str] = field(default_factory=dict)

    def get_venue_id_for_alias(self, name: str) -> str | None:
        """Resolve a venue acronym/alias to its canonical lowercase venue ID."""
        key = name.strip().lower()
        return self.alias_map.get(key)


def load_config(path: str | Path) -> Config:
    """Load configuration from a YAML file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}

    window_months = int(data.get("window_months", 4))
    slide_seconds = int(data.get("slide_seconds", 15))
    display_timezone = str(data.get("display_timezone", "PST")).strip()

    venues: dict[str, VenueConfig] = {}
    alias_map: dict[str, str] = {}

    raw_venues = data.get("venues", {})
    if isinstance(raw_venues, dict):
        for venue_id_raw, vdata in raw_venues.items():
            venue_id = str(venue_id_raw).strip().lower()
            if not isinstance(vdata, dict):
                continue
            primary_focus = str(vdata.get("primary_focus", ""))
            raw_aliases = vdata.get("aliases", [])
            aliases = tuple(str(a) for a in raw_aliases)

            v_config = VenueConfig(primary_focus=primary_focus, aliases=aliases)
            venues[venue_id] = v_config

            alias_map[venue_id] = venue_id
            for alias in aliases:
                alias_map[alias.strip().lower()] = venue_id

    location_overrides: dict[str, LocationOverride] = {}
    raw_loc_overrides = data.get("location_overrides", {})
    if isinstance(raw_loc_overrides, dict):
        for loc_key, ldata in raw_loc_overrides.items():
            if isinstance(ldata, dict):
                location_overrides[str(loc_key)] = LocationOverride(
                    city=str(ldata.get("city", "")),
                    country=str(ldata.get("country", "")),
                    display=str(ldata.get("display", "")),
                )

    return Config(
        window_months=window_months,
        slide_seconds=slide_seconds,
        display_timezone=display_timezone,
        venues=venues,
        location_overrides=location_overrides,
        alias_map=alias_map,
    )


def load_photo_overrides(path: str | Path) -> dict[str, PhotoOverride]:
    """Load photo overrides from a YAML file if it exists."""
    path = Path(path)
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}

    photos = data.get("photos", {})
    overrides: dict[str, PhotoOverride] = {}
    if isinstance(photos, dict):
        for loc_key, pdata in photos.items():
            if isinstance(pdata, dict):
                norm_key = str(loc_key).strip().lower()
                overrides[norm_key] = PhotoOverride(
                    pexels_id=pdata.get("pexels_id"),
                    file=pdata.get("file"),
                    credit=pdata.get("credit"),
                )
    return overrides
