import re
from dataclasses import dataclass

from confwall.config import LocationOverride


@dataclass(frozen=True)
class ParsedLocation:
    upstream_place: str
    display_place: str
    city: str | None
    country: str | None
    region: str | None
    location_key: str | None
    is_photographic: bool


def normalize_string(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def parse_location(
    place: str | None, overrides: dict[str, LocationOverride] | None = None
) -> ParsedLocation:
    """Pull city/country out of an upstream place string like "Seattle, WA, USA"."""
    if not place or not isinstance(place, str):
        return ParsedLocation(
            upstream_place="TBD",
            display_place="TBD",
            city=None,
            country=None,
            region=None,
            location_key=None,
            is_photographic=False,
        )

    upstream = place.strip()
    if not upstream:
        return ParsedLocation(
            upstream_place="TBD",
            display_place="TBD",
            city=None,
            country=None,
            region=None,
            location_key=None,
            is_photographic=False,
        )

    upper = upstream.upper()
    if upper in ("TBD", "VIRTUAL", "ONLINE") or any(
        kw in upper for kw in ("VIRTUAL", "ONLINE")
    ):
        return ParsedLocation(
            upstream_place=upstream,
            display_place=upstream,
            city=None,
            country=None,
            region=None,
            location_key=None,
            is_photographic=False,
        )

    if overrides:
        for k, ovr in overrides.items():
            if normalize_string(k) == normalize_string(upstream):
                city = ovr.city
                country = ovr.country
                display = ovr.display or f"{city}, {country}"
                loc_key = f"{normalize_string(city)}|{normalize_string(country)}"
                return ParsedLocation(
                    upstream_place=upstream,
                    display_place=display,
                    city=city,
                    country=country,
                    region=None,
                    location_key=loc_key,
                    is_photographic=True,
                )

    parts = [p.strip() for p in upstream.split(",") if p.strip()]

    if len(parts) == 1:
        # City-states and the like: "Singapore" is both the city and the country.
        single = parts[0]
        if normalize_string(single) in ("tbd", "virtual", "online"):
            return ParsedLocation(
                upstream_place=upstream,
                display_place=upstream,
                city=None,
                country=None,
                region=None,
                location_key=None,
                is_photographic=False,
            )
        city = single
        country = single
        loc_key = f"{normalize_string(city)}|{normalize_string(country)}"
        return ParsedLocation(
            upstream_place=upstream,
            display_place=upstream,
            city=city,
            country=country,
            region=None,
            location_key=loc_key,
            is_photographic=True,
        )

    city = parts[0]
    country = parts[-1]
    region = ", ".join(parts[1:-1]) if len(parts) > 2 else None

    norm_city = normalize_string(city)
    norm_country = normalize_string(country)
    loc_key = f"{norm_city}|{norm_country}"

    return ParsedLocation(
        upstream_place=upstream,
        display_place=upstream,
        city=city,
        country=country,
        region=region,
        location_key=loc_key,
        is_photographic=True,
    )
