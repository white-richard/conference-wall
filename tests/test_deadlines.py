from datetime import datetime, timedelta, timezone

from confwall.deadlines import (
    add_calendar_months,
    is_abstract_only,
    is_within_window,
    parse_deadline_datetime,
    parse_timezone,
    select_next_deadline,
)


def test_parse_timezone():
    # AoE -> -12:00
    tz_aoe = parse_timezone("AoE")
    assert tz_aoe is not None
    assert tz_aoe.utcoffset(None) == timedelta(hours=-12)

    # PST -> -08:00
    tz_pst = parse_timezone("PST")
    assert tz_pst is not None
    assert tz_pst.utcoffset(None) == timedelta(hours=-8)

    # PDT -> -07:00
    tz_pdt = parse_timezone("PDT")
    assert tz_pdt is not None
    assert tz_pdt.utcoffset(None) == timedelta(hours=-7)

    # UTC
    tz_utc = parse_timezone("UTC")
    assert tz_utc == timezone.utc

    # Positive UTC offset (UTC+5:30)
    tz_pos = parse_timezone("UTC+5:30")
    assert tz_pos is not None
    assert tz_pos.utcoffset(None) == timedelta(hours=5, minutes=30)

    # Negative UTC offset (UTC-8)
    tz_neg = parse_timezone("UTC-8")
    assert tz_neg is not None
    assert tz_neg.utcoffset(None) == timedelta(hours=-8)

    # Half hour raw offset (+05:30)
    tz_half = parse_timezone("+05:30")
    assert tz_half is not None
    assert tz_half.utcoffset(None) == timedelta(hours=5, minutes=30)

    # Invalid / Blank / TBD
    assert parse_timezone("INVALID_TZ_XYZ") is None
    assert parse_timezone("TBD") is None
    assert parse_timezone("") is None
    assert parse_timezone(None) is None


def test_parse_deadline_datetime():
    # AoE
    res = parse_deadline_datetime("2026-10-30 23:59:59", tz_override="AoE")
    assert res is not None
    dt_utc, dt_local, display_tz = res
    assert display_tz == "AoE"
    assert dt_local.hour == 23
    assert dt_utc.day == 31
    assert dt_utc.hour == 11

    # PST
    res_pst = parse_deadline_datetime("2026-10-30 23:59:59 PST")
    assert res_pst is not None
    dt_utc_pst, _, display_tz_pst = res_pst
    assert display_tz_pst == "PST"
    assert dt_utc_pst.hour == 7

    # TBD or blank
    assert parse_deadline_datetime("TBD") is None
    assert parse_deadline_datetime("") is None
    assert parse_deadline_datetime(None) is None
    assert parse_deadline_datetime("invalid date string") is None


def test_add_calendar_months():
    start_jan = datetime(2026, 1, 31, 12, 0, tzinfo=timezone.utc)
    assert add_calendar_months(start_jan, 4) == datetime(2026, 5, 31, 12, 0, tzinfo=timezone.utc)

    start_nov = datetime(2026, 11, 30, 15, 30, tzinfo=timezone.utc)
    assert add_calendar_months(start_nov, 4) == datetime(2027, 3, 30, 15, 30, tzinfo=timezone.utc)

    start_leap = datetime(2024, 2, 29, 0, 0, tzinfo=timezone.utc)
    assert add_calendar_months(start_leap, 4) == datetime(2024, 6, 29, 0, 0, tzinfo=timezone.utc)

    start_aug = datetime(2026, 8, 31, 23, 59, tzinfo=timezone.utc)
    assert add_calendar_months(start_aug, 4) == datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc)


def test_four_calendar_month_boundary():
    now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=timezone.utc)
    end_boundary = datetime(2026, 5, 31, 12, 0, 0, tzinfo=timezone.utc)

    assert is_within_window(now, now) is True
    assert is_within_window(end_boundary, now) is True
    assert is_within_window(now - timedelta(seconds=1), now) is False
    assert is_within_window(end_boundary + timedelta(seconds=1), now) is False

    mid = datetime(2026, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
    assert is_within_window(mid, now) is True


def test_is_abstract_only():
    assert is_abstract_only("Abstract Due") is True
    assert is_abstract_only("Abstract Registration") is True
    assert is_abstract_only("Abstract") is True
    assert is_abstract_only("Full Paper Submission") is False
    assert is_abstract_only("Round 1") is False
    assert is_abstract_only(None) is False


def test_select_next_deadline():
    now = datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)
    timeline = [
        {"deadline": "2026-06-01 23:59:59", "comment": "Past Round 1"},
        {"deadline": "2026-08-01 23:59:59", "comment": "Abstract Due"},
        {"deadline": "2026-09-15 23:59:59", "comment": "Round 2"},
        {"deadline": "2026-11-01 23:59:59", "comment": "Round 3"},
    ]

    d_info = select_next_deadline(timeline, default_tz_str="AoE", now=now)
    assert d_info is not None
    assert "Round 2" in d_info.deadline_comment
    assert "23:59 AoE" in d_info.deadline_comment
