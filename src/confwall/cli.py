import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from dateutil.parser import parse as parse_iso_datetime

from confwall import __version__
from confwall.conference_source import CCFConferenceSource
from confwall.config import load_config, load_dotenv, load_photo_overrides
from confwall.deadlines import (
    detect_publisher,
    is_within_window,
    select_next_deadline,
)
from confwall.locations import parse_location
from confwall.models import Slide
from confwall.photos import PhotoManager
from confwall.server import run_server
from confwall.site_builder import build_site_atomically

logger = logging.getLogger("confwall")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]


def run_refresh(
    config_path: str | Path = "config.yml",
    output_dir: str | Path = "build",
    refresh_photos: bool = False,
    now_arg: str | None = None,
    verbose: bool = False,
    snapshot_zip_bytes: bytes | None = None,
    photo_manager_override: PhotoManager | None = None,
    dotenv_path: str | Path | None = ".env",
) -> int:
    """Returns a process exit code."""
    if dotenv_path:
        load_dotenv(dotenv_path)

    setup_logging(verbose)

    if now_arg:
        try:
            now = parse_iso_datetime(now_arg)
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            else:
                now = now.astimezone(timezone.utc)
        except Exception as e:
            logger.error(f"Invalid ISO datetime for --now '{now_arg}': {e}")
            return 1
    else:
        now = datetime.now(timezone.utc)

    output_path = Path(output_dir)
    config_path = Path(config_path)

    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        return 1

    try:
        config = load_config(config_path, dotenv_path=dotenv_path)
    except Exception as e:
        logger.error(f"Failed to load configuration from {config_path}: {e}")
        return 1

    photo_overrides = load_photo_overrides("photo_overrides.yml")

    source = CCFConferenceSource()
    try:
        editions, total_source_records = source.load_editions(
            config=config, snapshot_zip_bytes=snapshot_zip_bytes
        )
    except Exception as e:
        logger.error(f"Failed to fetch or parse conference source: {e}")
        return 1

    matched_conf_editions_count = len(editions)

    slides: list[Slide] = []
    skipped_reasons: dict[str, int] = {
        "no_future_paper_deadline": 0,
        "outside_four_months": 0,
        "duplicate_edition": 0,
    }

    seen_keys: set[tuple[str, int, datetime]] = set()

    if photo_manager_override is not None:
        photo_mgr = photo_manager_override
    else:
        data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)
        photo_mgr = PhotoManager(
            manifest_path=data_dir / "photo_manifest.json",
            images_dir=output_path / "images",
            fallback_path=Path("assets/fallback-city.jpg"),
        )

    reused_photos_count = 0
    downloaded_photos_count = 0

    for ed in editions:
        primary_focus = config.get_primary_focus(ed.venue_id, ed.sub)
        if not primary_focus:
            continue

        d_info = select_next_deadline(
            ed.timeline, ed.timezone, now, display_tz_target=config.display_timezone
        )
        if d_info is None:
            skipped_reasons["no_future_paper_deadline"] += 1
            if verbose:
                logger.debug(f"Skipping {ed.acronym} {ed.year}: no parseable future paper deadline")
            continue

        if not is_within_window(d_info.deadline_utc, now, config.window_months):
            skipped_reasons["outside_four_months"] += 1
            if verbose:
                logger.debug(
                    f"Skipping {ed.acronym} {ed.year}: deadline {d_info.deadline_text} outside 4-month window"
                )
            continue

        dedup_key = (ed.venue_id, ed.year, d_info.deadline_utc)
        if dedup_key in seen_keys:
            skipped_reasons["duplicate_edition"] += 1
            continue
        seen_keys.add(dedup_key)

        loc = parse_location(ed.place, config.location_overrides)

        photo_path, photo_credit, source_url, is_new_download = (
            photo_mgr.resolve_photo_for_location(
                loc, overrides=photo_overrides, refresh_photos=refresh_photos
            )
        )

        if is_new_download:
            downloaded_photos_count += 1
        else:
            reused_photos_count += 1

        publisher_tag = detect_publisher(
            acronym=ed.acronym,
            full_name=ed.full_name,
            venue_id=ed.venue_id,
            aliases=config.venues[ed.venue_id].aliases if ed.venue_id in config.venues else (),
        )

        rank_core = ed.rank.get("core") if ed.rank else None
        rank_ccf = ed.rank.get("ccf") if ed.rank else None

        slide_id = f"{ed.venue_id}-{ed.year}"
        slide = Slide(
            id=slide_id,
            acronym=ed.acronym,
            full_name=ed.full_name,
            year=ed.year,
            conference_url=ed.link,
            deadline_utc=d_info.deadline_utc,
            deadline_text=d_info.deadline_text,
            deadline_comment=d_info.deadline_comment,
            location_display=loc.display_place,
            city=loc.city,
            country=loc.country,
            primary_focus=primary_focus,
            photo_path=photo_path,
            photo_credit=photo_credit,
            photo_source_url=source_url,
            publisher_tag=publisher_tag,
            abstract_deadline_text=d_info.abstract_deadline_text,
            rank_core=rank_core,
            rank_ccf=rank_ccf,
        )
        slides.append(slide)

    try:
        build_site_atomically(
            output_dir=output_path,
            slides=slides,
            images_dir=output_path / "images",
            slide_seconds=config.slide_seconds,
            window_months=config.window_months,
        )
    except Exception as e:
        logger.error(f"Failed to generate static site build: {e}")
        return 1

    print(f"Loaded {total_source_records} source records")
    print(f"Matched {matched_conf_editions_count} configured conference editions")
    print(f"Included {len(slides)} deadlines within four months")
    print(f"Reused {reused_photos_count} city photos")
    print(f"Downloaded {downloaded_photos_count} city photos")
    print(f"Generated {output_path}/")

    if verbose:
        logger.info("Skipped records breakdown:")
        for reason, count in skipped_reasons.items():
            logger.info(f"  - {reason}: {count}")

    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        prog="confwall",
        description="Browser slideshow for upcoming computer science conference deadlines",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    p_refresh = subparsers.add_parser(
        "refresh", help="Refresh conference deadlines and build static slideshow site"
    )
    p_refresh.add_argument("--config", default="config.yml", help="Path to config.yml")
    p_refresh.add_argument("--output", default="build", help="Target output directory")
    p_refresh.add_argument(
        "--refresh-photos",
        action="store_true",
        help="Ignore cached photo manifest and search Pexels again",
    )
    p_refresh.add_argument(
        "--now", help="Override current ISO datetime (for testing/debugging)"
    )
    p_refresh.add_argument(
        "--verbose", action="store_true", help="Enable verbose logging"
    )

    p_serve = subparsers.add_parser(
        "serve", help="Serve static slideshow site over HTTP"
    )
    p_serve.add_argument(
        "--directory", default="build", help="Directory to serve static site from"
    )
    p_serve.add_argument(
        "--host", default="127.0.0.1", help="Host IP address to bind to"
    )
    p_serve.add_argument(
        "--port", type=int, default=8000, help="Port number to listen on"
    )

    p_run = subparsers.add_parser(
        "run", help="Refresh slideshow data and serve static site"
    )
    p_run.add_argument("--config", default="config.yml", help="Path to config.yml")
    p_run.add_argument(
        "--output",
        default="build",
        help="Target output directory for static site",
    )
    p_run.add_argument(
        "--directory",
        default=None,
        help="Directory to serve (defaults to --output value)",
    )
    p_run.add_argument(
        "--refresh-photos",
        action="store_true",
        help="Ignore cached photo manifest and search Pexels again",
    )
    p_run.add_argument(
        "--now", help="Override current ISO datetime (for testing/debugging)"
    )
    p_run.add_argument(
        "--verbose", action="store_true", help="Enable verbose logging"
    )
    p_run.add_argument(
        "--host", default="127.0.0.1", help="Host IP address to bind to"
    )
    p_run.add_argument(
        "--port", type=int, default=8000, help="Port number to listen on"
    )

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "refresh":
        return run_refresh(
            config_path=args.config,
            output_dir=args.output,
            refresh_photos=args.refresh_photos,
            now_arg=args.now,
            verbose=args.verbose,
        )

    elif args.command == "serve":
        run_server(directory=args.directory, host=args.host, port=args.port)
        return 0

    elif args.command == "run":
        output_dir = args.output
        serve_dir = args.directory if args.directory else output_dir

        res = run_refresh(
            config_path=args.config,
            output_dir=output_dir,
            refresh_photos=args.refresh_photos,
            now_arg=args.now,
            verbose=args.verbose,
        )

        valid_build = (Path(serve_dir) / "slides.json").exists()

        if res != 0:
            logger.error(f"Refresh failed with exit code {res}.")
            if valid_build:
                logger.warning(f"Serving existing valid build from {serve_dir}...")
            else:
                logger.error("No valid build directory exists to serve. Exiting.")
                return 1

        run_server(directory=serve_dir, host=args.host, port=args.port)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
