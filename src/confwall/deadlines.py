"""Deadline parsing and filtering utilities for confwall."""

import calendar
import re
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from dateutil import tz

from confwall.models import DeadlineInfo


def parse_timezone(tz_str: str | None) -> timezone | tz.tzfile | None:
    """Parse a timezone string into a timezone object or fixed offset."""
    if not tz_str or not isinstance(tz_str, str):
        return None

    clean = tz_str.strip()
    if not clean or clean.upper() in ("TBD", "NONE", "UNKNOWN", "N/A"):
        return None

    upper = clean.upper()
    if upper in ("AOE", "ANYWHERE ON EARTH"):
        return timezone(timedelta(hours=-12))
    if upper in ("PST", "UTC-8", "UTC-0800", "-08:00"):
        return timezone(timedelta(hours=-8))
    if upper in ("PDT", "UTC-7", "UTC-0700", "-07:00"):
        return timezone(timedelta(hours=-7))
    if upper in ("PT", "PACIFIC", "US/PACIFIC", "AMERICA/LOS_ANGELES"):
        return tz.gettz("America/Los_Angeles")
    if upper in ("UTC", "UTC+0", "UTC-0", "Z", "GMT", "UTC+00:00", "UTC-00:00"):
        return timezone.utc

    # Match UTC/GMT fixed offsets like UTC-8, UTC+5:30, UTC+0530, -08:00, +05:30
    match = re.match(
        r"^(?:UTC|GMT)?\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?$", clean, re.IGNORECASE
    )
    if match:
        sign, hours, minutes = match.groups()
        h = int(hours)
        m = int(minutes) if minutes else 0
        total_minutes = h * 60 + m
        if sign == "-":
            total_minutes = -total_minutes
        return timezone(timedelta(minutes=total_minutes))

    # Try standard IANA timezone lookup via dateutil
    parsed_tz = tz.gettz(clean)
    return parsed_tz


def add_calendar_months(dt: datetime, months: int) -> datetime:
    """Add a given number of calendar months to a datetime, handling month-end clamping."""
    total_months = dt.month - 1 + months
    target_year = dt.year + total_months // 12
    target_month = total_months % 12 + 1
    max_days = calendar.monthrange(target_year, target_month)[1]
    target_day = min(dt.day, max_days)
    return dt.replace(year=target_year, month=target_month, day=target_day)


def parse_deadline_datetime(
    deadline_str: str | Any, tz_override: str | None = None
) -> tuple[datetime, datetime, str] | None:
    """
    Parse deadline string into (dt_utc, dt_local, display_tz_str).
    Returns None if malformed or unavailable.
    """
    if not deadline_str or not isinstance(deadline_str, str):
        return None

    clean = deadline_str.strip()
    if not clean or clean.upper() in ("TBD", "CANCELLED", "WITHDRAWN", "N/A"):
        return None

    tz_obj = None
    display_tz_str = tz_override or "UTC"

    match_tz = re.search(
        r"\s+([A-Za-z]+(?:/[A-Za-z_]+)?|UTC[+-]\d{1,2}(?::\d{2})?|AoE)$", clean, re.IGNORECASE
    )
    if match_tz:
        embedded_tz_str = match_tz.group(1)
        parsed_tz = parse_timezone(embedded_tz_str)
        if parsed_tz is not None:
            tz_obj = parsed_tz
            display_tz_str = embedded_tz_str
            clean = clean[: match_tz.start()].strip()

    if tz_obj is None and tz_override:
        tz_obj = parse_timezone(tz_override)
        display_tz_str = tz_override

    if tz_obj is None:
        tz_obj = timezone.utc
        display_tz_str = "UTC"

    date_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
    ]

    dt_naive = None
    for fmt in date_formats:
        try:
            dt_naive = datetime.strptime(clean, fmt)
            break
        except ValueError:
            continue

    if dt_naive is None:
        try:
            from dateutil.parser import parse as parse_date
            dt_parsed = parse_date(clean)
            if dt_parsed.tzinfo is not None:
                dt_utc = dt_parsed.astimezone(timezone.utc)
                return dt_utc, dt_parsed, display_tz_str
            dt_naive = dt_parsed
        except Exception:
            return None

    dt_local = dt_naive.replace(tzinfo=tz_obj)
    dt_utc = dt_local.astimezone(timezone.utc)
    return dt_utc, dt_local, display_tz_str


def is_abstract_only(comment: str | None) -> bool:
    """Determine if a deadline timeline item is an abstract-only deadline."""
    if not comment:
        return False
    c_lower = comment.lower()
    return bool(
        "abstract" in c_lower
        and not ("paper" in c_lower or "submission" in c_lower and "abstract" not in c_lower)
        and not ("full paper" in c_lower or "full" in c_lower)
    )


def format_deadline_display(dt_local: datetime, tz_str: str) -> str:
    """Format a deadline for display, e.g. 'October 30, 2026 · 23:59 PST'."""
    month_name = dt_local.strftime("%B")
    day = dt_local.day
    year = dt_local.year
    time_str = dt_local.strftime("%H:%M")
    return f"{month_name} {day}, {year} · {time_str} {tz_str}"


def detect_publisher(
    acronym: str,
    full_name: str,
    venue_id: str = "",
    aliases: Sequence[str] = (),
) -> str:
    """Detect publisher tag (IEEE, ACM, IEEE / ACM, USENIX, AAAI, ACL, IACR, VLDB, ISOC, Springer, SIAM, or Other)."""
    text_parts = [acronym, full_name, venue_id] + list(aliases)
    combined = " ".join(text_parts).upper()
    vid = venue_id.lower()
    acr = acronym.upper()

    has_ieee = "IEEE" in combined or vid in ("ispass", "bibm", "micro")
    has_acm = "ACM" in combined or vid in ("chi", "uist", "cscw", "iui", "ubicomp", "dis", "mobilehci", "tei", "facct", "kdd", "bcb", "asplos", "eurosys", "wsdm", "asiaccs", "sigcomm", "sigkdd", "siggraph")
    has_usenix = "USENIX" in combined or vid in ("osdi", "sosp", "nsdi", "fast", "atc")

    if has_ieee and has_acm:
        return "IEEE / ACM"
    if has_ieee:
        return "IEEE"
    if has_acm:
        return "ACM"
    if has_usenix:
        return "USENIX"
    if "AAAI" in combined or vid == "aaai":
        return "AAAI"
    if any(w in combined for w in ["ACL", "NAACL", "EACL", "EMNLP"]):
        return "ACL"
    if any(w in combined for w in ["IACR", "EUROCRYPT", "CHES", "CRYPTO", "ASIACRYPT"]):
        return "IACR"
    if "VLDB" in combined or vid == "vldb":
        return "VLDB"
    if "NDSS" in combined or vid == "ndss":
        return "ISOC"
    if "SPRINGER" in combined or "LNCS" in combined or vid in ("refsq", "lncs"):
        return "Springer"
    if "SIAM" in combined:
        return "SIAM"

    return "Other"


def detect_format(place: str) -> str:
    """Detect conference attendance format: 'In-Person', 'Remote', 'Hybrid', or 'TBD'."""
    if not place:
        return "TBD"
    clean = place.strip()
    if clean.upper() in ("TBD", "NONE", "N/A", "UNKNOWN"):
        return "TBD"

    c_lower = clean.lower()
    words = re.findall(r"\b[a-z]+\b", c_lower)
    remote_words = {"online", "virtual", "remote"}
    # Words that survive alongside a remote keyword without implying a physical venue.
    filler_words = remote_words | {
        "conference", "event", "venue", "meeting", "symposium", "workshop",
        "only", "fully", "entirely", "zoom", "webinar", "web",
        "tbc", "tbd", "format", "and", "or", "the", "in", "on", "a",
    }
    is_remote_kw = any(w in remote_words for w in words)
    location_words = [w for w in words if w not in filler_words]
    is_hybrid = "hybrid" in words or (is_remote_kw and len(location_words) > 0)

    if is_hybrid:
        return "Hybrid"
    if is_remote_kw:
        return "Remote"
    return "In-Person"


def select_next_deadline(
    timeline: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    default_tz_str: str | None,
    now: datetime,
    display_tz_target: str | None = "PST",
) -> DeadlineInfo | None:
    """
    Select the earliest remaining future paper deadline from a conference edition timeline.
    Converts deadline display to target timezone (e.g. PST/PDT).
    Also extracts associated abstract deadline if present.
    """
    if not timeline:
        return None

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    candidates: list[tuple[datetime, datetime, str, str | None, dict[str, Any]]] = []

    for item in timeline:
        if not isinstance(item, dict):
            continue

        comment = item.get("comment")
        comment_str = str(comment) if comment is not None else None

        if is_abstract_only(comment_str):
            continue

        raw_deadline = item.get("deadline")
        if not raw_deadline:
            continue

        item_tz = item.get("timezone") or default_tz_str

        parsed = parse_deadline_datetime(raw_deadline, tz_override=item_tz)
        if parsed is None:
            continue

        dt_utc, dt_local, display_tz_str = parsed

        if dt_utc >= now:
            candidates.append((dt_utc, dt_local, display_tz_str, comment_str, item))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    earliest_utc, earliest_local, source_tz_str, comment_str, selected_item = candidates[0]

    # Convert to target display timezone if configured (e.g. PST / PDT)
    if display_tz_target:
        clean_target = display_tz_target.strip().upper()
        if clean_target in ("PST", "PDT", "PT", "PACIFIC", "AMERICA/LOS_ANGELES"):
            target_tz = tz.gettz("America/Los_Angeles")
        else:
            target_tz = parse_timezone(display_tz_target) or timezone.utc

        dt_display = earliest_utc.astimezone(target_tz)
        tz_label = dt_display.strftime("%Z") or display_tz_target
    else:
        dt_display = earliest_local
        target_tz = parse_timezone(source_tz_str) or timezone.utc
        tz_label = source_tz_str

    deadline_text = format_deadline_display(dt_display, tz_label)

    # Append source timezone note if different
    if source_tz_str and source_tz_str.upper() != tz_label.upper():
        source_time_str = f"{earliest_local.strftime('%H:%M')} {source_tz_str}"
        if comment_str:
            comment_str = f"{comment_str} · ({source_time_str})"
        else:
            comment_str = f"({source_time_str})"

    # Look for associated abstract deadline
    abstract_dt_utc: datetime | None = None
    abstract_dt_text: str | None = None

    raw_abs_dl = selected_item.get("abstract_deadline") or selected_item.get("abstract deadline")
    if raw_abs_dl:
        item_tz = selected_item.get("timezone") or default_tz_str
        parsed_abs = parse_deadline_datetime(raw_abs_dl, tz_override=item_tz)
        if parsed_abs is not None:
            abs_utc, abs_local, _ = parsed_abs
            abstract_dt_utc = abs_utc
            abs_display = abs_utc.astimezone(target_tz) if display_tz_target else abs_local
            abstract_dt_text = format_deadline_display(abs_display, tz_label)

    if not abstract_dt_text:
        # Search timeline for prior abstract-only items preceding selected paper deadline
        abs_candidates = []
        for item in timeline:
            if not isinstance(item, dict):
                continue
            c_str = str(item.get("comment", ""))
            if is_abstract_only(c_str) or "abstract" in c_str.lower():
                raw_dl = item.get("deadline")
                if raw_dl:
                    item_tz = item.get("timezone") or default_tz_str
                    p_abs = parse_deadline_datetime(raw_dl, tz_override=item_tz)
                    if p_abs is not None and p_abs[0] <= earliest_utc:
                        abs_candidates.append(p_abs)
        if abs_candidates:
            abs_candidates.sort(key=lambda x: x[0], reverse=True)
            abs_utc, abs_local, _ = abs_candidates[0]
            abstract_dt_utc = abs_utc
            abs_display = abs_utc.astimezone(target_tz) if display_tz_target else abs_local
            abstract_dt_text = format_deadline_display(abs_display, tz_label)

    return DeadlineInfo(
        deadline_utc=earliest_utc,
        deadline_text=deadline_text,
        deadline_comment=comment_str,
        tz_str=tz_label,
        abstract_deadline_utc=abstract_dt_utc,
        abstract_deadline_text=abstract_dt_text,
    )


def is_within_four_months(
    deadline_utc: datetime, now: datetime, window_months: int = 4
) -> bool:
    """
    Check if deadline_utc falls within now and now + window_months calendar months (inclusive).
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    if deadline_utc.tzinfo is None:
        deadline_utc = deadline_utc.replace(tzinfo=timezone.utc)
    else:
        deadline_utc = deadline_utc.astimezone(timezone.utc)

    end_boundary = add_calendar_months(now, window_months)
    return now <= deadline_utc <= end_boundary
