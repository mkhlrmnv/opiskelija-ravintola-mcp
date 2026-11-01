"""Async TTL cache for menus; concurrent fetches of the same key are collapsed into one."""

from __future__ import annotations

import asyncio
import datetime as dt
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from ravintola_mcp.models import Lang, Menu

CacheKey = tuple[str, dt.date, Lang]

DEFAULT_TTL_S = 30 * 60
DEFAULT_ERROR_TTL_S = 2 * 60


@dataclass(frozen=True, slots=True)
class _Entry:
    menu: Menu
    expires_at: float


class MenuCache:
    """Caches ``Menu`` objects by (restaurant_id, date, lang).

    Menus carrying ``error`` expire sooner so a transient failure is retried quickly.
    ``clock`` is injectable for tests.
    """

    def __init__(
        self,
        *,
        ttl: float = DEFAULT_TTL_S,
        error_ttl: float = DEFAULT_ERROR_TTL_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl
        self._error_ttl = error_ttl
        self._clock = clock
        self._entries: dict[CacheKey, _Entry] = {}
        self._locks: dict[CacheKey, asyncio.Lock] = {}

    def get(self, key: CacheKey) -> Menu | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if self._clock() >= entry.expires_at:
            del self._entries[key]
            return None
        return entry.menu

    def put(self, key: CacheKey, menu: Menu) -> None:
        now = self._clock()
        self._evict_expired(now)
        ttl = self._error_ttl if menu.error else self._ttl
        self._entries[key] = _Entry(menu, now + ttl)

    async def get_or_fetch(self, key: CacheKey, fetch: Callable[[], Awaitable[Menu]]) -> Menu:
        """Return the cached menu, or run ``fetch`` once even if many callers ask at the same time.

        Waiters re-check the cache after the lock is released, so they reuse the leader's result.
        If ``fetch`` raises, nothing is cached and the next caller tries again.
        """
        if (menu := self.get(key)) is not None:
            return menu
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            if (menu := self.get(key)) is not None:
                return menu
            menu = await fetch()
            self.put(key, menu)
            return menu

    def _evict_expired(self, now: float) -> None:
        for key in [k for k, entry in self._entries.items() if now >= entry.expires_at]:
            del self._entries[key]
