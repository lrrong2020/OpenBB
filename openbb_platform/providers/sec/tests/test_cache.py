"""Unit tests for the unified SEC disk cache (``openbb_sec.utils.cache``).

These tests exercise the cache wrapper directly with an isolated temp-directory
``FanoutCache`` and mocked transport, since the fetcher suite always runs with
``use_cache=False`` and never touches the caching code paths.
"""

import asyncio
import contextlib

import pytest

from openbb_sec.utils import cache as cache_module


@pytest.fixture
def temp_cache(tmp_path, monkeypatch):
    """Provide an isolated cache rooted in a temp directory.

    Forces a fresh process-wide singleton bound to ``tmp_path`` and restores the
    previous one on teardown so the global state does not leak across tests.
    """
    monkeypatch.setattr(
        cache_module, "get_cache_directory", lambda: str(tmp_path / "sec")
    )
    monkeypatch.delenv(cache_module.SIZE_LIMIT_ENV_VAR, raising=False)
    previous = cache_module._cache
    cache_module._cache = None
    yield cache_module
    if cache_module._cache is not None:
        with contextlib.suppress(Exception):
            cache_module._cache.close()
    cache_module._cache = previous


# ---------------------------------------------------------------------------
# _parse_size / get_size_limit
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, cache_module.DEFAULT_SIZE_LIMIT),
        ("", cache_module.DEFAULT_SIZE_LIMIT),
        (4096, 4096),
        (0, cache_module.DEFAULT_SIZE_LIMIT),
        (-10, cache_module.DEFAULT_SIZE_LIMIT),
        ("1024B", 1024),
        ("100KB", 100 * 1024),
        ("512MB", 512 * 1024**2),
        ("8GB", 8 * 1024**3),
        ("1.5TB", int(1.5 * 1024**4)),
        ("2 gb", 2 * 1024**3),  # spaces + lowercase normalized
        ("12345", 12345),  # bare number
        ("badGB", cache_module.DEFAULT_SIZE_LIMIT),  # non-numeric w/ suffix
        ("notanumber", cache_module.DEFAULT_SIZE_LIMIT),  # non-numeric bare
    ],
)
def test_parse_size(value, expected):
    """_parse_size handles bytes, suffixed strings, and bad input."""
    assert cache_module._parse_size(value) == expected


def test_get_size_limit_env(monkeypatch):
    """get_size_limit reads the override env var, defaulting when unset."""
    monkeypatch.delenv(cache_module.SIZE_LIMIT_ENV_VAR, raising=False)
    assert cache_module.get_size_limit() == cache_module.DEFAULT_SIZE_LIMIT
    monkeypatch.setenv(cache_module.SIZE_LIMIT_ENV_VAR, "256MB")
    assert cache_module.get_size_limit() == 256 * 1024**2


def test_get_cache_directory():
    """get_cache_directory points at a 'sec' subdirectory."""
    assert cache_module.get_cache_directory().replace("\\", "/").endswith("/sec")


# ---------------------------------------------------------------------------
# get_cache singleton
# ---------------------------------------------------------------------------


def test_get_cache_is_singleton(temp_cache):
    """get_cache builds the cache once and reuses it."""
    first = temp_cache.get_cache()
    second = temp_cache.get_cache()
    assert first is second
    assert temp_cache.get_size_limit() == temp_cache.DEFAULT_SIZE_LIMIT


# ---------------------------------------------------------------------------
# _make_key / _is_empty
# ---------------------------------------------------------------------------


def test_make_key():
    """_make_key encodes method, url, and suffix."""
    assert cache_module._make_key("http://x") == "GET http://x"
    assert cache_module._make_key("http://x", "post") == "POST http://x"
    assert cache_module._make_key("http://x", suffix=" ::text") == "GET http://x ::text"


@pytest.mark.parametrize(
    "value, empty",
    [
        (None, True),
        ({}, True),
        ([], True),
        ({"a": 1}, False),
        ([1], False),
        ("text", False),
        (0, False),
    ],
)
def test_is_empty(value, empty):
    """_is_empty flags None and empty containers only."""
    assert cache_module._is_empty(value) is empty


# ---------------------------------------------------------------------------
# _cache_set / _cache_get
# ---------------------------------------------------------------------------


def test_cache_set_get_roundtrip(temp_cache):
    """Values written can be read back; misses return None."""
    temp_cache._cache_set("k", {"a": 1}, None)
    assert temp_cache._cache_get("k") == {"a": 1}
    assert temp_cache._cache_get("missing") is None


def test_cache_get_swallows_backend_errors(temp_cache, monkeypatch):
    """A backend failure on read degrades to a miss, never raises."""

    class _Boom:
        def get(self, *a, **k):
            raise RuntimeError("backend down")

        def set(self, *a, **k):
            raise RuntimeError("backend down")

    monkeypatch.setattr(temp_cache, "get_cache", _Boom)
    assert temp_cache._cache_get("k") is None
    temp_cache._cache_set("k", "v", None)  # must not raise


# ---------------------------------------------------------------------------
# cached_request (async, amake_request)
# ---------------------------------------------------------------------------


def _patch_amake(monkeypatch, return_value, counter):
    async def _fake(url, method="GET", **kwargs):
        counter.append((url, method))
        return return_value

    monkeypatch.setattr(
        "openbb_core.provider.utils.helpers.amake_request", _fake, raising=False
    )


def test_cached_request_bypass(temp_cache, monkeypatch):
    """use_cache=False calls the transport directly and never caches."""
    calls: list = []
    _patch_amake(monkeypatch, {"ok": 1}, calls)
    result = asyncio.run(temp_cache.cached_request("http://x", use_cache=False))
    assert result == {"ok": 1}
    assert len(calls) == 1
    # Nothing stored.
    assert temp_cache._cache_get(temp_cache._make_key("http://x")) is None


def test_cached_request_miss_then_hit(temp_cache, monkeypatch):
    """First call hits the transport and stores; second is served from cache."""
    calls: list = []
    _patch_amake(monkeypatch, {"ok": 1}, calls)
    first = asyncio.run(temp_cache.cached_request("http://x"))
    second = asyncio.run(temp_cache.cached_request("http://x"))
    assert first == second == {"ok": 1}
    assert len(calls) == 1  # transport only invoked once


def test_cached_request_empty_not_stored(temp_cache, monkeypatch):
    """Empty responses are returned but not cached."""
    calls: list = []
    _patch_amake(monkeypatch, {}, calls)
    asyncio.run(temp_cache.cached_request("http://x"))
    assert temp_cache._cache_get(temp_cache._make_key("http://x")) is None


def test_cached_request_post(temp_cache, monkeypatch):
    """POST requests forward the method to the transport."""
    calls: list = []
    _patch_amake(monkeypatch, [1, 2], calls)
    asyncio.run(temp_cache.cached_request("http://x", method="POST"))
    assert calls == [("http://x", "POST")]


# ---------------------------------------------------------------------------
# cached_text / cached_bytes (sync, make_request)
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, text="body", content=b"body", status_ok=True):
        self.text = text
        self.content = content
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            raise RuntimeError("HTTP error")


def _patch_make(monkeypatch, response, counter):
    def _fake(url, **kwargs):
        counter.append(url)
        return response

    monkeypatch.setattr(
        "openbb_core.provider.utils.helpers.make_request", _fake, raising=False
    )


def test_cached_text_miss_then_hit(temp_cache, monkeypatch):
    """cached_text caches the body and serves the second call from cache."""
    calls: list = []
    _patch_make(monkeypatch, _FakeResponse(text="hello"), calls)
    assert temp_cache.cached_text("http://x") == "hello"
    assert temp_cache.cached_text("http://x") == "hello"
    assert len(calls) == 1


def test_cached_text_bypass(temp_cache, monkeypatch):
    """use_cache=False always calls the transport."""
    calls: list = []
    _patch_make(monkeypatch, _FakeResponse(text="hi"), calls)
    temp_cache.cached_text("http://x", use_cache=False)
    temp_cache.cached_text("http://x", use_cache=False)
    assert len(calls) == 2


def test_cached_text_raise_for_status(temp_cache, monkeypatch):
    """A non-2xx response raises when raise_for_status is True."""
    _patch_make(monkeypatch, _FakeResponse(status_ok=False), [])
    with pytest.raises(RuntimeError):
        temp_cache.cached_text("http://x")


def test_cached_text_empty_not_stored(temp_cache, monkeypatch):
    """Empty bodies are returned but not cached."""
    _patch_make(monkeypatch, _FakeResponse(text=""), [])
    assert temp_cache.cached_text("http://x") == ""
    assert (
        temp_cache._cache_get(temp_cache._make_key("http://x", suffix=" ::text"))
        is None
    )


def test_cached_bytes_miss_then_hit(temp_cache, monkeypatch):
    """cached_bytes caches binary content."""
    calls: list = []
    _patch_make(monkeypatch, _FakeResponse(content=b"\x00\x01"), calls)
    assert temp_cache.cached_bytes("http://x") == b"\x00\x01"
    assert temp_cache.cached_bytes("http://x") == b"\x00\x01"
    assert len(calls) == 1


def test_cached_bytes_no_raise_for_status(temp_cache, monkeypatch):
    """raise_for_status=False returns the body even on an error response."""
    _patch_make(monkeypatch, _FakeResponse(content=b"x", status_ok=False), [])
    assert temp_cache.cached_bytes("http://x", raise_for_status=False) == b"x"


# ---------------------------------------------------------------------------
# aget_cached / aset_cached / clear_cache
# ---------------------------------------------------------------------------


def test_aget_aset_roundtrip(temp_cache):
    """Async key-value helpers round-trip through the cache."""
    asyncio.run(temp_cache.aset_cached("k", [1, 2, 3]))
    assert asyncio.run(temp_cache.aget_cached("k")) == [1, 2, 3]
    assert asyncio.run(temp_cache.aget_cached("missing")) is None


def test_clear_cache(temp_cache):
    """clear_cache removes all entries and reports the count."""
    temp_cache._cache_set("a", 1, None)
    temp_cache._cache_set("b", 2, None)
    removed = temp_cache.clear_cache()
    assert removed >= 2
    assert temp_cache._cache_get("a") is None


def test_clear_cache_error_returns_zero(temp_cache, monkeypatch):
    """clear_cache returns 0 when the backend errors."""

    class _Boom:
        def clear(self, *a, **k):
            raise RuntimeError("backend down")

    monkeypatch.setattr(temp_cache, "get_cache", _Boom)
    assert temp_cache.clear_cache() == 0
