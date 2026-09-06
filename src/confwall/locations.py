import re
from dataclasses import dataclass

from confwall.config import LocationOverride

# "City, <state>" with no country listed should resolve to the USA, not treat the
# state as the country (which broke Pexels searches and split cities like Boulder
# and Seattle across multiple location_keys depending on how upstream wrote it).
_US_STATE_ABBRS = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id", "il", "in",
    "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv",
    "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc", "sd", "tn",
    "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy", "dc",
}
_US_STATE_NAMES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut",
    "delaware", "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa",
    "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan",
    "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york", "north carolina",
    "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island",
    "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont",
    "virginia", "washington", "west virginia", "wisconsin", "wyoming",
    "district of columbia",
}

# Different upstream records spell the same country differently ("USA" vs "United
# States"), which produced separate location_keys (and separate Pexels searches and
# manifest cache entries) for the same real city.
_COUNTRY_ALIASES = {
    "usa": "USA",
    "us": "USA",
    "u.s.": "USA",
    "u.s.a.": "USA",
    "united states": "USA",
    "united states of america": "USA",
    "uk": "UK",
    "u.k.": "UK",
    "united kingdom": "UK",
}


def _canonical_country(country: str) -> str:
    return _COUNTRY_ALIASES.get(normalize_string(country), country)


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

    if region is None:
        norm_second = normalize_string(country)
        if norm_second in _US_STATE_NAMES or norm_second in _US_STATE_ABBRS:
            region = country
            country = "USA"

    country = _canonical_country(country)

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
