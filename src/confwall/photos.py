"""Photo resolution, Pexels API integration, scoring, caching, and overrides for confwall."""

import io
import json
import logging
import os
import shutil
from datetime import UTC
from pathlib import Path
from typing import Any

from PIL import Image

from confwall.config import PhotoOverride
from confwall.http_client import HttpClient
from confwall.locations import ParsedLocation
from confwall.models import PhotoManifestEntry

logger = logging.getLogger(__name__)

PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
PEXELS_PHOTO_URL = "https://api.pexels.com/v1/photos/{id}"


def score_pexels_candidate(
    photo: dict[str, Any], city: str, country: str, region: str | None = None
) -> int:
    """Deterministically score a Pexels photo candidate."""
    score = 0
    alt = str(photo.get("alt", "")).lower()
    width = int(photo.get("width", 0))
    height = int(photo.get("height", 1)) or 1

    # City in alt text
    if city.lower() in alt:
        score += 10

    # Country or region in alt text
    if country.lower() in alt or (region and region.lower() in alt):
        score += 4

    # Keywords
    if "aerial" in alt:
        score += 5
    if "skyline" in alt:
        score += 4
    if "cityscape" in alt:
        score += 4
    if "downtown" in alt:
        score += 3
    if "panorama" in alt:
        score += 2

    # Aspect ratio & dimensions
    ratio = width / height
    if ratio >= 1.6:
        score += 2
    if width >= 1920:
        score += 2

    # Penalties
    if "portrait" in alt:
        score -= 5
    if "person" in alt or "people" in alt:
        score -= 5
    if "food" in alt:
        score -= 4
    if "indoor" in alt or "interior" in alt:
        score -= 4
    if "hotel room" in alt:
        score -= 4
    if "airport" in alt:
        score -= 3
    if "sign" in alt:
        score -= 3

    return score


class PhotoManager:
    """Manages photo searches, caching in manifest, overrides, and local downloads."""

    def __init__(
        self,
        manifest_path: Path,
        images_dir: Path,
        fallback_path: Path,
        http_client: HttpClient | None = None,
    ) -> None:
        self.manifest_path = Path(manifest_path)
        self.images_dir = Path(images_dir)
        self.fallback_path = Path(fallback_path)
        self.http_client = http_client or HttpClient()
        self.manifest: dict[str, PhotoManifestEntry] = self._load_manifest()

    def _load_manifest(self) -> dict[str, PhotoManifestEntry]:
        if not self.manifest_path.exists():
            return {}
        try:
            with self.manifest_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            result = {}
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, dict):
                        result[k] = PhotoManifestEntry.from_dict(v)
            return result
        except Exception as e:
            logger.warning(f"Failed to load photo manifest from {self.manifest_path}: {e}")
            return {}

    def save_manifest(self) -> None:
        """Save photo manifest atomically."""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = self.manifest_path.with_suffix(".tmp")
        data = {k: v.to_dict() for k, v in self.manifest.items()}
        with tmp_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp_file.replace(self.manifest_path)

    def resolve_photo_for_location(
        self,
        location: ParsedLocation,
        overrides: dict[str, PhotoOverride] | None = None,
        refresh_photos: bool = False,
    ) -> tuple[str, str, str | None, bool]:
        """
        Resolve photo for a parsed location.
        Returns tuple: (relative_image_path, credit_text, source_url, is_new_download).
        """
        self.images_dir.mkdir(parents=True, exist_ok=True)

        # 1. Non-photographic location or missing location
        if not location.is_photographic or not location.location_key:
            fallback_rel = self._ensure_fallback_in_images()
            return fallback_rel, "Fallback Image", None, False

        loc_key = location.location_key
        override = (overrides or {}).get(loc_key)

        # 2. Handle override if present
        if override:
            if override.file:
                # Copy override file to images_dir
                override_src = Path(override.file)
                if override_src.exists():
                    clean_name = loc_key.replace("|", "-")
                    filename = f"{clean_name}-override{override_src.suffix}"
                    dest_file = self.images_dir / filename
                    shutil.copy2(override_src, dest_file)
                    credit = override.credit or f"Photo for {location.display_place}"
                    return f"images/{filename}", credit, None, False

            if override.pexels_id:
                # Fetch specific pexels ID
                api_key = os.environ.get("PEXELS_API_KEY")
                if api_key:
                    try:
                        entry = self._fetch_pexels_photo_by_id(
                            override.pexels_id, loc_key, location, api_key
                        )
                        if entry:
                            self.manifest[loc_key] = entry
                            self.save_manifest()
                            return entry.local_file, f"Photo by {entry.photographer} on Pexels", entry.source_url, True
                    except Exception as e:
                        logger.warning(f"Failed to fetch pexels override ID {override.pexels_id}: {e}")

        # 3. Check cached manifest entry if not refresh_photos
        if not refresh_photos and loc_key in self.manifest:
            entry = self.manifest[loc_key]
            local_target = self.images_dir.parent / entry.local_file
            if local_target.exists() and self._validate_image_file(local_target):
                return (
                    entry.local_file,
                    f"Photo by {entry.photographer} on Pexels" if entry.photographer else "Pexels Photo",
                    entry.source_url,
                    False,
                )
            # Local file missing or corrupt -> try redownloading recorded photo before new search
            if entry.source_url or entry.photo_id:
                redownloaded = self._redownload_manifest_photo(entry)
                if redownloaded:
                    return (
                        entry.local_file,
                        f"Photo by {entry.photographer} on Pexels" if entry.photographer else "Pexels Photo",
                        entry.source_url,
                        True,
                    )

        # 4. Search Pexels if API key available
        api_key = os.environ.get("PEXELS_API_KEY")
        if api_key and location.city and location.country:
            entry = self._search_and_select_pexels_photo(location, loc_key, api_key)
            if entry:
                self.manifest[loc_key] = entry
                self.save_manifest()
                return (
                    entry.local_file,
                    f"Photo by {entry.photographer} on Pexels",
                    entry.source_url,
                    True,
                )

        # 5. Fallback image if search produced no results or no API key
        fallback_rel = self._ensure_fallback_in_images()
        return fallback_rel, "Fallback Image", None, False

    def _ensure_fallback_in_images(self) -> str:
        dest = self.images_dir / "fallback-city.jpg"
        if not dest.exists() and self.fallback_path.exists():
            shutil.copy2(self.fallback_path, dest)
        return "images/fallback-city.jpg"

    def _validate_image_bytes(self, data: bytes) -> bool:
        try:
            img = Image.open(io.BytesIO(data))
            img.verify()
            return True
        except Exception:
            return False

    def _validate_image_file(self, path: Path) -> bool:
        try:
            with Image.open(path) as img:
                img.verify()
            return True
        except Exception:
            return False

    def _redownload_manifest_photo(self, entry: PhotoManifestEntry) -> bool:
        dest = self.images_dir.parent / entry.local_file
        dest.parent.mkdir(parents=True, exist_ok=True)
        if entry.source_url:
            try:
                img_bytes = self.http_client.get_bytes(entry.source_url)
                if self._validate_image_bytes(img_bytes):
                    dest.write_bytes(img_bytes)
                    return True
            except Exception as e:
                logger.warning(f"Failed to redownload photo from source_url {entry.source_url}: {e}")
        return False

    def _fetch_pexels_photo_by_id(
        self, pexels_id: int | str, loc_key: str, location: ParsedLocation, api_key: str
    ) -> PhotoManifestEntry | None:
        url = PEXELS_PHOTO_URL.format(id=pexels_id)
        headers = {"Authorization": api_key}
        data = self.http_client.get_json(url, headers=headers)
        if not isinstance(data, dict):
            return None

        return self._download_and_create_entry(data, loc_key, location, f"pexels_id:{pexels_id}")

    def _search_and_select_pexels_photo(
        self, location: ParsedLocation, loc_key: str, api_key: str
    ) -> PhotoManifestEntry | None:
        city = location.city or ""
        country = location.country or ""
        region = location.region

        # Search query hierarchy
        queries = []
        if region:
            queries.append(f"{city} {region} {country} aerial skyline")
        queries.append(f"{city} {country} aerial skyline")
        queries.append(f"{city} {country} cityscape")
        queries.append(f"{city} {country} skyline")
        queries.append(f"{city} {country} downtown")

        headers = {"Authorization": api_key}

        for query in queries:
            params = {
                "query": query,
                "orientation": "landscape",
                "size": "large",
                "per_page": 20,
            }
            try:
                res = self.http_client.get_json(PEXELS_SEARCH_URL, headers=headers, params=params)
                photos = res.get("photos", []) if isinstance(res, dict) else []
                if not photos:
                    continue

                # Filter and score photos
                candidates: list[tuple[int, int, dict[str, Any]]] = []
                for idx, photo in enumerate(photos):
                    if not isinstance(photo, dict):
                        continue
                    w = int(photo.get("width", 0))
                    h = int(photo.get("height", 0))
                    # Requirements: HTTPS URL, Landscape (w > h), w >= 1200
                    if w <= h or w < 1200:
                        continue
                    src = photo.get("src", {})
                    img_url = src.get("landscape") or src.get("large2x") or src.get("original") or src.get("large")
                    if not img_url or not str(img_url).startswith("https://"):
                        continue

                    score = score_pexels_candidate(photo, city, country, region)
                    candidates.append((score, idx, photo))

                if candidates:
                    # Sort by score desc, then by original API index asc
                    candidates.sort(key=lambda c: (-c[0], c[1]))
                    best_photo = candidates[0][2]
                    entry = self._download_and_create_entry(best_photo, loc_key, location, query)
                    if entry:
                        return entry

            except Exception as e:
                logger.warning(f"Pexels query '{query}' failed: {e}")
                continue

        return None

    def _download_and_create_entry(
        self, photo: dict[str, Any], loc_key: str, location: ParsedLocation, query: str
    ) -> PhotoManifestEntry | None:
        photo_id = photo.get("id")
        src = photo.get("src", {})
        img_url = (
            src.get("landscape")
            or src.get("large2x")
            or src.get("original")
            or src.get("large")
        )
        if not img_url:
            return None

        # Download image bytes and validate
        try:
            img_bytes = self.http_client.get_bytes(str(img_url))
            if not self._validate_image_bytes(img_bytes):
                logger.warning(f"Downloaded image for photo {photo_id} failed Pillow validation")
                return None
        except Exception as e:
            logger.warning(f"Failed downloading image for photo {photo_id}: {e}")
            return None

        clean_key = loc_key.replace("|", "-")
        filename = f"{clean_key}-{photo_id}.jpg"
        dest_path = self.images_dir / filename
        dest_path.write_bytes(img_bytes)

        rel_path = f"images/{filename}"

        photographer = str(photo.get("photographer", "Unknown"))
        photographer_url = str(photo.get("photographer_url", ""))
        source_url = str(photo.get("url", img_url))
        w = int(photo.get("width", 0))
        h = int(photo.get("height", 0))
        from datetime import datetime
        now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        return PhotoManifestEntry(
            location_key=loc_key,
            provider="pexels",
            photo_id=photo_id,
            query=query,
            photographer=photographer,
            photographer_url=photographer_url,
            source_url=source_url,
            local_file=rel_path,
            width=w,
            height=h,
            selected_at=now_iso,
        )
