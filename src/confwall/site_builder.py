"""Static site generator with cross-platform atomic directory replacement for confwall."""

import json
import logging
import shutil
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from confwall.models import Slide

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def _safe_rmtree(path: Path) -> None:
    """Helper to remove directory trees safely, handling Windows file lock delays."""
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
    except Exception:
        time.sleep(0.1)
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Could not remove directory {path}: {e}")


def slide_to_dict(slide: Slide) -> dict[str, Any]:
    """Convert slide dataclass to dictionary, ensuring POSIX forward slashes for web photo paths."""
    photo_path = Path(slide.photo_path).as_posix()
    return {
        "id": slide.id,
        "acronym": slide.acronym,
        "full_name": slide.full_name,
        "year": slide.year,
        "conference_url": slide.conference_url,
        "deadline_utc": slide.deadline_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "deadline_text": slide.deadline_text,
        "deadline_comment": slide.deadline_comment,
        "location_display": slide.location_display,
        "city": slide.city,
        "country": slide.country,
        "primary_focus": slide.primary_focus,
        "photo_path": photo_path,
        "photo_credit": slide.photo_credit,
        "photo_source_url": slide.photo_source_url,
        "publisher_tag": slide.publisher_tag,
        "format_tag": slide.format_tag,
        "abstract_deadline_text": slide.abstract_deadline_text,
        "keywords": list(slide.keywords),
        "rank_core": slide.rank_core,
        "rank_ccf": slide.rank_ccf,
    }


def build_site_atomically(
    output_dir: Path,
    slides: list[Slide],
    images_dir: Path,
    slide_seconds: int = 15,
) -> None:
    """
    Generate static site into a temporary directory, then replace target output_dir.
    Supports atomic replacement on POSIX and fallback directory sync on Windows.
    If generation fails, existing output_dir remains untouched.
    """
    output_dir = Path(output_dir)
    images_dir = Path(images_dir)

    # Sort slides by deadline_utc
    sorted_slides = sorted(slides, key=lambda s: s.deadline_utc)

    # Create temporary directory on same parent filesystem if possible
    parent_dir = output_dir.parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=parent_dir, prefix=".confwall_build_") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)

        # 1. Copy static assets (index.html, app.js, style.css)
        for static_file in STATIC_DIR.glob("*"):
            if static_file.is_file():
                shutil.copy2(static_file, tmp_dir / static_file.name)

        # 2. Copy images directory
        tmp_images_dir = tmp_dir / "images"
        tmp_images_dir.mkdir(parents=True, exist_ok=True)
        if images_dir.exists():
            for img in images_dir.glob("*"):
                if img.is_file():
                    shutil.copy2(img, tmp_images_dir / img.name)

        # 3. Create slides.json
        now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        slides_data = {
            "generated_at": now_iso,
            "slide_seconds": slide_seconds,
            "slides": [slide_to_dict(s) for s in sorted_slides],
        }
        slides_json_path = tmp_dir / "slides.json"
        with slides_json_path.open("w", encoding="utf-8") as f:
            json.dump(slides_data, f, indent=2, ensure_ascii=False)

        # 4. Replace output_dir safely across OS platforms
        if output_dir.exists():
            old_backup = parent_dir / f".confwall_old_{output_dir.name}"
            _safe_rmtree(old_backup)
            renamed = False
            try:
                output_dir.rename(old_backup)
                renamed = True
            except Exception as e:
                logger.debug(f"Direct rename unsupported or locked, using directory sync: {e}")

            if renamed:
                try:
                    shutil.copytree(tmp_dir, output_dir)
                    _safe_rmtree(old_backup)
                except Exception as e:
                    if output_dir.exists():
                        _safe_rmtree(output_dir)
                    old_backup.rename(output_dir)
                    raise RuntimeError(f"Atomic build failed to replace {output_dir}: {e}") from e
            else:
                shutil.copytree(tmp_dir, output_dir, dirs_exist_ok=True)
        else:
            shutil.copytree(tmp_dir, output_dir)

    logger.info(f"Successfully generated build at {output_dir}")
