import io
import logging
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from confwall.config import Config
from confwall.http_client import HttpClient
from confwall.models import ConferenceEdition

logger = logging.getLogger(__name__)

CCF_SNAPSHOT_URL = (
    "https://github.com/ccfddl/ccf-deadlines/archive/refs/heads/main.zip"
)


class CCFConferenceSource:
    def __init__(self, http_client: HttpClient | None = None) -> None:
        self.http_client = http_client or HttpClient()

    def fetch_records_from_zip(
        self, zip_bytes: bytes, config: Config
    ) -> tuple[list[ConferenceEdition], int]:
        """Returns (matched editions, total records seen)."""
        matched_editions: list[ConferenceEdition] = []
        total_source_records = 0

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            for name in z.namelist():
                if "/conference/" in name and name.endswith((".yml", ".yaml")):
                    try:
                        content = z.read(name).decode("utf-8")
                        editions, count = self._parse_yaml_content(
                            content, config, source_name=name
                        )
                        total_source_records += count
                        matched_editions.extend(editions)
                    except Exception as e:
                        logger.warning(f"Failed to parse source file {name}: {e}")

        return matched_editions, total_source_records

    def fetch_records_from_directory(
        self, dir_path: Path, config: Config
    ) -> tuple[list[ConferenceEdition], int]:
        """Same as fetch_records_from_zip, against an unpacked checkout."""
        matched_editions: list[ConferenceEdition] = []
        total_source_records = 0

        conf_dir = dir_path / "conference" if (dir_path / "conference").exists() else dir_path

        for path in conf_dir.rglob("*"):
            if path.is_file() and path.suffix in (".yml", ".yaml"):
                try:
                    content = path.read_text(encoding="utf-8")
                    editions, count = self._parse_yaml_content(
                        content, config, source_name=path.name
                    )
                    total_source_records += count
                    matched_editions.extend(editions)
                except Exception as e:
                    logger.warning(f"Failed to parse source file {path}: {e}")

        return matched_editions, total_source_records

    def load_editions(
        self, config: Config, snapshot_zip_bytes: bytes | None = None
    ) -> tuple[list[ConferenceEdition], int]:
        if snapshot_zip_bytes is not None:
            return self.fetch_records_from_zip(snapshot_zip_bytes, config)

        logger.info(f"Downloading CCF-Deadlines snapshot from {CCF_SNAPSHOT_URL}")
        zip_bytes = self.http_client.get_bytes(CCF_SNAPSHOT_URL)
        return self.fetch_records_from_zip(zip_bytes, config)

    def _parse_yaml_content(
        self, content: str, config: Config, source_name: str
    ) -> tuple[list[ConferenceEdition], int]:
        parsed = yaml.safe_load(content)
        if not parsed:
            return [], 0

        items: Sequence[dict[str, Any]]
        if isinstance(parsed, list):
            items = parsed
        elif isinstance(parsed, dict):
            items = [parsed]
        else:
            return [], 0

        record_count = len(items)
        matched_editions: list[ConferenceEdition] = []

        for item in items:
            if not isinstance(item, dict):
                continue

            title = str(item.get("title", "")).strip()
            filename_stem = Path(source_name).stem.strip()
            sub = str(item.get("sub", "")).strip().upper()

            venue_id = (
                config.get_venue_id_for_alias(title)
                or config.get_venue_id_for_alias(filename_stem)
                or (title.lower() if title else filename_stem.lower())
            )

            focus = config.get_primary_focus(venue_id, sub_category=sub)
            if not focus:
                continue

            rank_raw = item.get("rank")
            rank = dict(rank_raw) if isinstance(rank_raw, dict) else None

            full_name = str(item.get("description", title)).strip() or title
            confs = item.get("confs", [])
            if not isinstance(confs, list):
                continue

            for conf in confs:
                if not isinstance(conf, dict):
                    continue

                year_val = conf.get("year")
                try:
                    year = int(year_val)
                except (ValueError, TypeError):
                    continue

                link = str(conf.get("link", ""))
                timeline_raw = conf.get("timeline", [])
                if not isinstance(timeline_raw, list):
                    timeline_raw = []

                timeline = tuple(
                    dict(t) for t in timeline_raw if isinstance(t, dict)
                )
                tz_str = conf.get("timezone")
                place = str(conf.get("place", "TBD"))

                edition = ConferenceEdition(
                    venue_id=venue_id,
                    acronym=title or filename_stem,
                    full_name=full_name,
                    year=year,
                    link=link,
                    timeline=timeline,
                    timezone=str(tz_str) if tz_str else None,
                    place=place,
                    sub=sub,
                    rank=rank,
                )
                matched_editions.append(edition)

        return matched_editions, record_count
