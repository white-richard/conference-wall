"""Data models for confwall."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Slide:
    id: str
    acronym: str
    full_name: str
    year: int
    conference_url: str
    deadline_utc: datetime
    deadline_text: str
    deadline_comment: str | None
    location_display: str
    city: str | None
    country: str | None
    primary_focus: str
    photo_path: str
    photo_credit: str
    photo_source_url: str | None
    publisher_tag: str = "Other"
    format_tag: str = "In-Person"
    abstract_deadline_text: str | None = None
    rank_core: str | None = None
    rank_ccf: str | None = None


@dataclass(frozen=True)
class PhotoManifestEntry:
    location_key: str
    provider: str
    photo_id: str | int
    query: str
    photographer: str
    photographer_url: str
    source_url: str
    local_file: str
    width: int
    height: int
    selected_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "location_key": self.location_key,
            "provider": self.provider,
            "photo_id": self.photo_id,
            "query": self.query,
            "photographer": self.photographer,
            "photographer_url": self.photographer_url,
            "source_url": self.source_url,
            "local_file": self.local_file,
            "width": self.width,
            "height": self.height,
            "selected_at": self.selected_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PhotoManifestEntry":
        return cls(
            location_key=data["location_key"],
            provider=data["provider"],
            photo_id=data["photo_id"],
            query=data.get("query", ""),
            photographer=data["photographer"],
            photographer_url=data.get("photographer_url", ""),
            source_url=data.get("source_url", ""),
            local_file=data["local_file"],
            width=data.get("width", 0),
            height=data.get("height", 0),
            selected_at=data.get("selected_at", ""),
        )


@dataclass(frozen=True)
class ConferenceEdition:
    venue_id: str
    acronym: str
    full_name: str
    year: int
    link: str
    timeline: tuple[dict[str, Any], ...]
    timezone: str | None
    place: str
    sub: str | None = None
    rank: dict[str, str] | None = None


@dataclass(frozen=True)
class DeadlineInfo:
    deadline_utc: datetime
    deadline_text: str
    deadline_comment: str | None
    tz_str: str | None
    abstract_deadline_utc: datetime | None = None
    abstract_deadline_text: str | None = None

