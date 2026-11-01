import asyncio
from collections.abc import Awaitable, Callable

import pytest

from ravintola_mcp.cache import MenuCache
from ravintola_mcp.models import Lang, Menu
from tests.fakes import DAY, make_menu


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


KEY = ("a-bloc", DAY, "en")


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def cache(clock: FakeClock) -> MenuCache:
    return MenuCache(ttl=30 * 60, error_ttl=2 * 60, clock=clock)


def test_successful_menu_expires_after_ttl(cache: MenuCache, clock: FakeClock) -> None:
    cache.put(KEY, make_menu("a-bloc", "A Bloc"))
    clock.now += 30 * 60 - 1
    assert cache.get(KEY) is not None
    clock.now += 1
    assert cache.get(KEY) is None


def test_error_menu_expires_after_error_ttl(cache: MenuCache, clock: FakeClock) -> None:
    cache.put(KEY, make_menu("a-bloc", "A Bloc", error="timeout"))
    clock.now += 2 * 60 - 1
    assert cache.get(KEY) is not None
    clock.now += 1
    assert cache.get(KEY) is None


def test_expired_entries_are_evicted_on_put(cache: MenuCache, clock: FakeClock) -> None:
    cache.put(KEY, make_menu("a-bloc", "A Bloc"))
    clock.now += 31 * 60
    cache.put(("tuas", DAY, "en"), make_menu("tuas", "TUAS"))
    assert KEY not in cache._entries


async def test_get_or_fetch_calls_fetch_once_while_fresh(cache: MenuCache) -> None:
    calls = 0

    async def fetch() -> Menu:
        nonlocal calls
        calls += 1
        return make_menu("a-bloc", "A Bloc")

    first = await cache.get_or_fetch(KEY, fetch)
    second = await cache.get_or_fetch(KEY, fetch)
    assert calls == 1
    assert first is second


async def test_concurrent_requests_for_same_key_share_one_fetch(cache: MenuCache) -> None:
    calls = 0

    async def fetch() -> Menu:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return make_menu("a-bloc", "A Bloc")

    results = await asyncio.gather(*(cache.get_or_fetch(KEY, fetch) for _ in range(5)))
    assert calls == 1
    assert all(r is results[0] for r in results)


async def test_different_keys_are_fetched_independently(cache: MenuCache) -> None:
    fetched: list[Lang] = []

    def fetcher(lang: Lang) -> Callable[[], Awaitable[Menu]]:
        async def fetch() -> Menu:
            fetched.append(lang)
            await asyncio.sleep(0)
            return make_menu("a-bloc", "A Bloc", lang=lang)

        return fetch

    await asyncio.gather(
        cache.get_or_fetch(("a-bloc", DAY, "en"), fetcher("en")),
        cache.get_or_fetch(("a-bloc", DAY, "fi"), fetcher("fi")),
    )
    assert sorted(fetched) == ["en", "fi"]


async def test_failed_fetch_is_not_cached_and_is_retried(cache: MenuCache) -> None:
    attempts = 0

    async def flaky() -> Menu:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("down")
        return make_menu("a-bloc", "A Bloc")

    with pytest.raises(ConnectionError):
        await cache.get_or_fetch(KEY, flaky)
    menu = await cache.get_or_fetch(KEY, flaky)
    assert menu.error is None
    assert attempts == 2
