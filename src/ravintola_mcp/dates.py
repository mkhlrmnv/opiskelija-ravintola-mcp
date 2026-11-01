"""Parsing of user-supplied dates, relative to the current day in Helsinki."""

from __future__ import annotations

import datetime as dt
import re
from zoneinfo import ZoneInfo

HELSINKI = ZoneInfo("Europe/Helsinki")

_WEEKDAYS: dict[str, int] = {
    "monday": 0,
    "maanantai": 0,
    "tuesday": 1,
    "tiistai": 1,
    "wednesday": 2,
    "keskiviikko": 2,
    "thursday": 3,
    "torstai": 3,
    "friday": 4,
    "perjantai": 4,
    "saturday": 5,
    "lauantai": 5,
    "sunday": 6,
    "sunnuntai": 6,
}
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def helsinki_today() -> dt.date:
    return dt.datetime.now(HELSINKI).date()


def resolve_date(value: str | None, today: dt.date | None = None) -> dt.date:
    """Turn 'today', 'tomorrow', a weekday (English or Finnish) or ISO date into a date.

    Weekday names resolve to the next occurrence on or after ``today``.
    """
    if today is None:
        today = helsinki_today()
    text = (value or "").strip().lower()
    if text in ("", "today"):
        return today
    if text == "tomorrow":
        return today + dt.timedelta(days=1)
    if text == "yesterday":
        return today - dt.timedelta(days=1)
    if text in _WEEKDAYS:
        return today + dt.timedelta(days=(_WEEKDAYS[text] - today.weekday()) % 7)
    if _ISO_DATE.fullmatch(text):
        try:
            return dt.date.fromisoformat(text)
        except ValueError:
            pass
    raise ValueError(
        f"Unrecognised date {value!r}. Use 'today', 'tomorrow', 'yesterday', a weekday name "
        "(English or Finnish, e.g. 'friday' or 'perjantai') or an ISO date such as '2026-11-30'."
    )
