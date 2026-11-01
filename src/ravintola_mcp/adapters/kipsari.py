"""Kipsari (Otaniemi, vegan student restaurants) via the RSS menu feeds on www.kipsari.com.

Each location publishes its lunch menu as WordPress RSS, e.g. ``/rss-vare/`` (Finnish) and
``/rss-vare-english/`` (English). A feed covers one ISO week: one item per weekday, titled with
the date, whose description holds the hot main dish plus the standing salad and bread lines as
``<span>``s. Diet codes trail a dish in parentheses, e.g. ``(*, VE, G)``; ``*`` means the dish
meets nutrition recommendations. The site publishes no nutrition data, so no macros are set.

Restaurant ``config`` keys: ``feed`` (Finnish feed slug, default ``rss-vare``) and ``feed_en``
(English feed slug, default ``<feed>-english``).
"""

from __future__ import annotations

import datetime as dt
import re
import xml.etree.ElementTree as ET
from typing import Final

import httpx
from bs4 import BeautifulSoup

from ravintola_mcp.adapters.base import AdapterError, MenuAdapter, slugify
from ravintola_mcp.models import Dish, Lang, Menu, Restaurant

BASE_URL: Final = "https://www.kipsari.com"
DEFAULT_FEED: Final = "rss-vare"
_FI_DATE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")  # "Ma, 02.11.2026"
_EN_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")  # "Mon, 2026-11-02"
_DIET_SUFFIX = re.compile(r"\s*\(((?:\*|[A-Z]{1,4})(?:\s*,\s*(?:\*|[A-Z]{1,4}))*)\)$")


class KipsariAdapter(MenuAdapter):
    provider = "kipsari"

    async def fetch_menu(
        self, restaurant: Restaurant, day: dt.date, lang: Lang, client: httpx.AsyncClient
    ) -> Menu:
        feed = restaurant.config.get("feed", DEFAULT_FEED)
        english_feed = restaurant.config.get("feed_en", f"{feed}-english")
        # Requested language first, Finnish as the fallback; the Finnish feed must exist.
        sources: list[tuple[Lang, str]] = [
            (lang, _feed_url(english_feed if lang == "en" else feed))
        ]
        if lang == "en":
            sources.append(("fi", _feed_url(feed)))

        for menu_lang, url in sources:
            channel = await _load_channel(client, url)
            if channel is None:
                if menu_lang == "fi":
                    raise AdapterError(f"Kipsari menu feed not found: {url}")
                continue
            item = _find_item(channel, day)
            if item is None:
                continue
            notes: list[str] = []
            if menu_lang != lang:
                notes.append("No English menu for this date; showing the Finnish menu.")
            dishes = _dishes(item)
            if not dishes:
                notes.append("The feed lists this date without any dishes.")
            return Menu(
                restaurant_id=restaurant.id,
                restaurant_name=restaurant.name,
                date=day,
                lang=menu_lang,
                dishes=dishes,
                source_url=url,
                notes=notes,
            )

        return Menu(
            restaurant_id=restaurant.id,
            restaurant_name=restaurant.name,
            date=day,
            lang=lang,
            source_url=sources[0][1],
            notes=[
                f"No lunch menu is listed for {day:%d.%m.%Y}. The restaurant may be closed, "
                "and the feed only covers one week at a time."
            ],
        )


def _feed_url(slug: str) -> str:
    return f"{BASE_URL}/{slug}/"


async def _load_channel(client: httpx.AsyncClient, url: str) -> ET.Element | None:
    """The feed's ``<channel>``, or None when the feed does not exist (HTTP 404)."""
    response = await client.get(url)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise AdapterError(f"Kipsari feed is not valid XML ({url}): {exc}") from exc
    channel = root.find("channel")
    if channel is None:
        raise AdapterError(f"Kipsari feed has no channel ({url})")
    return channel


def _find_item(channel: ET.Element, day: dt.date) -> ET.Element | None:
    for item in channel.findall("item"):
        if _item_date(item.findtext("title", default="")) == day:
            return item
    return None


def _item_date(title: str) -> dt.date | None:
    try:
        if match := _FI_DATE.search(title):
            return dt.date(int(match[3]), int(match[2]), int(match[1]))
        if match := _EN_DATE.search(title):
            return dt.date(int(match[1]), int(match[2]), int(match[3]))
    except ValueError:
        return None
    return None


def _dishes(item: ET.Element) -> list[Dish]:
    html = item.findtext("description", default="")
    dishes: list[Dish] = []
    used_ids: set[str] = set()
    for span in BeautifulSoup(html, "html.parser").find_all("span"):
        text = _repair_mojibake(span.get_text(" ", strip=True))
        if not text:
            continue
        name, diets = _split_diets(text)
        dish_id = _unique_id(slugify(name) or "dish", used_ids)
        dishes.append(Dish(id=dish_id, name=name, diets=diets))
    return dishes


def _split_diets(text: str) -> tuple[str, list[str]]:
    match = _DIET_SUFFIX.search(text)
    if match is None:
        return text, []
    codes = [code.strip() for code in match.group(1).split(",")]
    return text[: match.start()].strip(), codes


def _repair_mojibake(text: str) -> str:
    """Undo UTF-8 that was double-encoded as Latin-1 (the feed sends 'VihreÃ¤' for 'Vihreä')."""
    try:
        return text.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return text


def _unique_id(base: str, used: set[str]) -> str:
    candidate, suffix = base, 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate
