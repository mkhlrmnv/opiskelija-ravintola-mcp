import datetime as dt

import pytest

from ravintola_mcp.dates import HELSINKI, resolve_date

MONDAY = dt.date(2026, 11, 2)
SUNDAY = dt.date(2026, 11, 8)


def test_monday_fixture_is_a_monday() -> None:
    assert MONDAY.weekday() == 0


@pytest.mark.parametrize("value", [None, "", "  ", "today", "Today"])
def test_today_forms(value: str | None) -> None:
    assert resolve_date(value, MONDAY) == MONDAY


def test_tomorrow_and_yesterday() -> None:
    assert resolve_date("tomorrow", MONDAY) == dt.date(2026, 11, 3)
    assert resolve_date("YESTERDAY", MONDAY) == dt.date(2026, 11, 1)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("monday", dt.date(2026, 11, 2)),
        ("Tuesday", dt.date(2026, 11, 3)),
        ("keskiviikko", dt.date(2026, 11, 4)),
        ("TORSTAI", dt.date(2026, 11, 5)),
        ("friday", dt.date(2026, 11, 6)),
        ("lauantai", dt.date(2026, 11, 7)),
        ("sunday", SUNDAY),
        ("sunnuntai", SUNDAY),
    ],
)
def test_weekday_is_next_occurrence_on_or_after_today(value: str, expected: dt.date) -> None:
    assert resolve_date(value, MONDAY) == expected


def test_weekday_equal_to_today_is_today() -> None:
    assert resolve_date("sunday", SUNDAY) == SUNDAY
    assert resolve_date("monday", SUNDAY) == dt.date(2026, 11, 9)


def test_iso_date() -> None:
    assert resolve_date("2026-12-24", MONDAY) == dt.date(2026, 12, 24)


@pytest.mark.parametrize(
    "value", ["2026-13-01", "2026-02-30", "31.12.2026", "funday", "next monday"]
)
def test_invalid_values_raise_helpful_error(value: str) -> None:
    with pytest.raises(ValueError, match="Unrecognised date"):
        resolve_date(value, MONDAY)


def test_default_today_is_helsinki_date() -> None:
    assert resolve_date(None) == dt.datetime.now(HELSINKI).date()
