"""Kipsari adapter: offline parsing of saved RSS feeds, plus one live check (``-m live``)."""

from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import pytest

from ravintola_mcp.adapters.base import USER_AGENT, AdapterError
from ravintola_mcp.adapters.kipsari import KipsariAdapter
from ravintola_mcp.models import Lang, Menu
from ravintola_mcp.restaurants import RESTAURANTS

FIXTURES = Path(__file__).parent / "fixtures" / "kipsari"
FI_URL = "https://www.kipsari.com/rss-vare/"
EN_URL = "https://www.kipsari.com/rss-vare-english/"
KIPSARI = next(r for r in RESTAURANTS if r.id == "kipsari")
SUNDAY = dt.date(2026, 11, 1)
MONDAY = dt.date(2026, 11, 2)
THURSDAY = dt.date(2026, 11, 5)
NEXT_MONDAY = dt.date(2026, 11, 9)


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


FI_FEED = _fixture("rss-vare-fi.xml")
EN_FEED = _fixture("rss-vare-en.xml")


def _client(feeds: dict[str, bytes]) -> httpx.AsyncClient:
    """Serve canned feeds by URL; any other URL answers 404, as WordPress does."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = feeds.get(str(request.url))
        if body is None:
            return httpx.Response(404, text="<html>Not found</html>")
        return httpx.Response(200, content=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _without_item(feed: bytes, title_fragment: str) -> bytes:
    root = ET.fromstring(feed)
    channel = root.find("channel")
    assert channel is not None
    for item in channel.findall("item"):
        if title_fragment in (item.findtext("title") or ""):
            channel.remove(item)
    return ET.tostring(root)


def _synthetic_feed(*items: tuple[str, str]) -> bytes:
    entries = "".join(
        f"<item><title>{title}</title><description><![CDATA[{body}]]></description></item>"
        for title, body in items
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>'
        f"<title>Kipsari Väre</title><description>Lounas – vko 45</description>{entries}"
        "</channel></rss>"
    ).encode()


async def _menu(feeds: dict[str, bytes], day: dt.date, lang: Lang = "fi") -> Menu:
    async with _client(feeds) as client:
        return await KipsariAdapter().fetch_menu(KIPSARI, day, lang, client)


async def test_finnish_monday_menu_is_parsed() -> None:
    menu = await _menu({FI_URL: FI_FEED}, MONDAY)

    assert menu.error is None
    assert menu.lang == "fi"
    assert menu.source_url == FI_URL
    assert menu.notes == []
    assert [d.name for d in menu.dishes] == [
        "Vihreä curry soijasuikaleiden kera, riisi-moniviljaseos",
        "Salaattilounas",
        "Leipäateria",
    ]
    main = menu.dishes[0]
    assert main.id == "vihrea-curry-soijasuikaleiden-kera-riisi-moniviljaseos"
    assert main.diets == ["*", "VE"]
    assert main.allergens == []
    assert main.price is None


async def test_selects_the_requested_day() -> None:
    menu = await _menu({FI_URL: FI_FEED}, THURSDAY)

    assert menu.dishes[0].name == "Pinaattiohukaiset, perunamuusia, puolukka-omenasurvos"
    assert menu.dishes[0].diets == ["*", "VE", "G"]


async def test_english_menu_comes_from_the_english_feed() -> None:
    menu = await _menu({FI_URL: FI_FEED, EN_URL: EN_FEED}, MONDAY, lang="en")

    assert menu.lang == "en"
    assert menu.source_url == EN_URL
    assert menu.notes == []
    assert menu.dishes[0].name == "Green curry with soya stripes, rice and multi grains"
    assert menu.dishes[0].diets == ["*", "VE"]
    assert [d.name for d in menu.dishes[1:]] == ["Salad lunch", "Bread meal"]


async def test_missing_english_feed_falls_back_to_finnish() -> None:
    menu = await _menu({FI_URL: FI_FEED}, MONDAY, lang="en")

    assert menu.lang == "fi"
    assert menu.source_url == FI_URL
    assert menu.dishes[0].name.startswith("Vihreä curry")
    assert any("English" in note for note in menu.notes)


async def test_day_missing_from_english_feed_falls_back_to_finnish() -> None:
    en_feed = _without_item(EN_FEED, "2026-11-02")

    menu = await _menu({FI_URL: FI_FEED, EN_URL: en_feed}, MONDAY, lang="en")

    assert menu.lang == "fi"
    assert menu.dishes[0].name.startswith("Vihreä curry")
    assert any("English" in note for note in menu.notes)


@pytest.mark.parametrize("day", [SUNDAY, dt.date(2026, 11, 7), NEXT_MONDAY])
async def test_day_without_menu_gives_empty_dishes_and_note(day: dt.date) -> None:
    menu = await _menu({FI_URL: FI_FEED}, day)

    assert menu.error is None
    assert menu.dishes == []
    assert menu.date == day
    assert len(menu.notes) == 1
    assert "No lunch menu" in menu.notes[0]


async def test_missing_day_with_english_request_keeps_english_lang() -> None:
    menu = await _menu({FI_URL: FI_FEED, EN_URL: EN_FEED}, SUNDAY, lang="en")

    assert menu.dishes == []
    assert menu.lang == "en"


async def test_missing_finnish_feed_is_an_error() -> None:
    with pytest.raises(AdapterError, match="rss-vare"):
        await _menu({}, MONDAY)


async def test_macros_are_never_invented() -> None:
    menu = await _menu({FI_URL: FI_FEED}, MONDAY)

    assert menu.macros_available is False
    assert all(d.macros is None for d in menu.dishes)


async def test_dish_lines_keep_non_diet_parentheses_and_ids_stay_unique() -> None:
    feed = _synthetic_feed(
        (
            "Ma, 02.11.2026",
            "<span>Kasvispihvi (lemon) (*, VE)</span>"
            "<span>Salad (Caesar)</span><span>Salaattilounas</span><span>Salaattilounas</span>",
        )
    )

    menu = await _menu({FI_URL: feed}, MONDAY)

    assert [(d.name, d.diets) for d in menu.dishes] == [
        ("Kasvispihvi (lemon)", ["*", "VE"]),
        ("Salad (Caesar)", []),
        ("Salaattilounas", []),
        ("Salaattilounas", []),
    ]
    assert [d.id for d in menu.dishes] == [
        "kasvispihvi-lemon",
        "salad-caesar",
        "salaattilounas",
        "salaattilounas-2",
    ]


@pytest.mark.live
async def test_live_feed_returns_a_menu() -> None:
    async with httpx.AsyncClient(
        timeout=15.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        menu = await KipsariAdapter().fetch_menu(KIPSARI, dt.date.today(), "fi", client)

    assert menu.error is None
    assert menu.restaurant_id == "kipsari"
    assert menu.source_url == FI_URL
    assert all(d.id and d.name for d in menu.dishes)
