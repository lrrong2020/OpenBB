"""Unit tests for ``openbb_sec.utils.frames``.

These exercise the frame URL-building and parsing functions directly with
crafted synthetic inputs and mocked transport, covering branches the
fetcher/VCR suites never reach.  No real HTTP is performed: ``cached_request``
and ``fetch_data`` are patched at the import site (``openbb_sec.utils.frames``).
"""

import asyncio
from unittest.mock import patch

import pytest
from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.utils.errors import EmptyDataError

import openbb_sec.utils.frames as fr


def test_fetch_data_expire_by_persist():
    """fetch_data sets a 24h expiry for historical frames and None when persisting.

    cached_request is imported at module scope in frames, so it is patched there.
    """
    seen = {}

    async def _fake_cr(url, headers=None, use_cache=True, expire=None):
        seen["expire"] = expire
        return {"ok": True}

    with patch.object(fr, "cached_request", _fake_cr):
        # persist=False -> historical, 24h TTL.
        out = asyncio.run(fr.fetch_data("http://x", True, False))
        assert seen["expire"] == 3600 * 24
        assert out == {"ok": True}
        # persist=True -> current-year frame, no expiry.
        asyncio.run(fr.fetch_data("http://x", True, True))
        assert seen["expire"] is None


def _frame_companies():
    from pandas import DataFrame

    return DataFrame(
        {
            "cik": ["320193", "789019"],
            "symbol": ["AAPL", "MSFT"],
            "name": ["Apple", "Microsoft"],
        }
    )


_FRAME_RESP = {
    "ccp": "CY2023Q1",
    "tag": "Revenues",
    "label": "Revenues",
    "description": "desc",
    "taxonomy": "us-gaap",
    "uom": "USD",
    "pts": 2,
    "data": [{"cik": 320193, "val": 100}, {"cik": 789019, "val": 200}],
}


def test_get_frame_quarter():
    """get_frame builds a quarterly URL, sorts data, and maps CIK->symbol."""

    async def _fetch(url, use_cache, persist):
        assert url.endswith("CY2023Q1.json")
        return _FRAME_RESP

    async def _companies(use_cache=True):
        return _frame_companies()

    with (
        patch.object(fr, "fetch_data", _fetch),
        patch.object(fr, "get_all_companies", _companies),
    ):
        res = asyncio.run(fr.get_frame(fact="Revenues", year=2023, fiscal_period="q1"))
    assert res["metadata"]["frame"] == "CY2023Q1"
    assert res["metadata"]["unit"] == "USD"
    # Sorted by val descending -> MSFT (200) first.
    assert res["data"][0]["symbol"] == "MSFT"
    assert res["data"][0]["fact"] == "Revenues"


def test_get_frame_defaults_to_current_period():
    """With no year/period, get_frame derives them from today's date."""
    from datetime import datetime

    captured = {}

    async def _fetch(url, use_cache, persist):
        captured["url"] = url
        captured["persist"] = persist
        return _FRAME_RESP

    async def _companies(use_cache=True):
        return _frame_companies()

    with (
        patch.object(fr, "fetch_data", _fetch),
        patch.object(fr, "get_all_companies", _companies),
    ):
        asyncio.run(fr.get_frame(fact="Revenues"))
    year = datetime.now().date().year
    assert f"CY{year}" in captured["url"]
    assert captured["persist"] is True  # current year persists


def test_get_frame_period_without_year_defaults_year():
    """A fiscal_period with no year defaults the year to the current calendar year."""
    from datetime import datetime

    captured = {}

    async def _fetch(url, use_cache, persist):
        captured["url"] = url
        return _FRAME_RESP

    async def _companies(use_cache=True):
        return _frame_companies()

    with (
        patch.object(fr, "fetch_data", _fetch),
        patch.object(fr, "get_all_companies", _companies),
    ):
        asyncio.run(fr.get_frame(fact="Revenues", year=None, fiscal_period="q1"))
    year = datetime.now().date().year
    # quarter is set (Q1) so the default-both branch is skipped; only year defaults.
    assert captured["url"].endswith(f"CY{year}Q1.json")


def test_get_frame_shares_units():
    """A SHARES_FACTS fact forces the 'shares' unit in the URL."""
    captured = {}

    async def _fetch(url, use_cache, persist):
        captured["url"] = url
        return _FRAME_RESP

    async def _companies(use_cache=True):
        return _frame_companies()

    with (
        patch.object(fr, "fetch_data", _fetch),
        patch.object(fr, "get_all_companies", _companies),
    ):
        asyncio.run(
            fr.get_frame(
                fact="WeightedAverageNumberOfSharesOutstandingBasic", year=2023
            )
        )
    assert "/shares/" in captured["url"]


def test_get_frame_per_share_units_instantaneous():
    """A USD_PER_SHARE_FACTS fact sets the per-share unit; instantaneous adds 'I'."""
    captured = {}

    async def _fetch(url, use_cache, persist):
        captured["url"] = url
        return _FRAME_RESP

    async def _companies(use_cache=True):
        return _frame_companies()

    with (
        patch.object(fr, "fetch_data", _fetch),
        patch.object(fr, "get_all_companies", _companies),
    ):
        asyncio.run(
            fr.get_frame(fact="EarningsPerShareBasic", year=2023, instantaneous=True)
        )
    assert "/USD-per-shares/" in captured["url"]
    assert captured["url"].endswith("I.json")


def test_get_frame_instantaneous_retry():
    """An instantaneous request that fails retries without the 'I' suffix."""
    urls = []

    async def _fetch(url, use_cache, persist):
        urls.append(url)
        if url.endswith("I.json"):
            raise RuntimeError("no instant frame")
        return _FRAME_RESP

    async def _companies(use_cache=True):
        return _frame_companies()

    with (
        patch.object(fr, "fetch_data", _fetch),
        patch.object(fr, "get_all_companies", _companies),
    ):
        with pytest.warns(Warning):
            res = asyncio.run(
                fr.get_frame(
                    fact="Revenues",
                    year=2023,
                    fiscal_period="q1",
                    instantaneous=True,
                )
            )
    assert urls[0].endswith("I.json")
    assert urls[1].endswith("Q1.json")
    assert res["metadata"]["tag"] == "Revenues"


def test_get_frame_quarter_retry_instantaneous():
    """A quarterly request that fails retries as instantaneous."""
    urls = []

    async def _fetch(url, use_cache, persist):
        urls.append(url)
        if url.endswith("I.json"):
            return _FRAME_RESP
        raise RuntimeError("no quarter frame")

    async def _companies(use_cache=True):
        return _frame_companies()

    with (
        patch.object(fr, "fetch_data", _fetch),
        patch.object(fr, "get_all_companies", _companies),
    ):
        with pytest.warns(Warning):
            res = asyncio.run(
                fr.get_frame(fact="Revenues", year=2023, fiscal_period="q1")
            )
    assert urls[0].endswith("Q1.json")
    assert urls[1].endswith("Q1I.json")
    assert res["data"]  # parsed successfully on retry


def test_get_frame_instantaneous_double_failure_raises():
    """An instantaneous request whose retry also fails raises OpenBBError."""

    async def _fetch(url, use_cache, persist):
        raise RuntimeError("nothing here")

    async def _companies(use_cache=True):
        return _frame_companies()

    with (
        patch.object(fr, "fetch_data", _fetch),
        patch.object(fr, "get_all_companies", _companies),
    ):
        with pytest.warns(Warning):
            with pytest.raises(OpenBBError, match="No frame was found"):
                asyncio.run(
                    fr.get_frame(
                        fact="Revenues",
                        year=2023,
                        fiscal_period="q1",
                        instantaneous=True,
                    )
                )


def test_get_frame_quarter_double_failure_raises():
    """A quarterly request whose instantaneous retry also fails raises OpenBBError."""

    async def _fetch(url, use_cache, persist):
        raise RuntimeError("nothing here")

    async def _companies(use_cache=True):
        return _frame_companies()

    with (
        patch.object(fr, "fetch_data", _fetch),
        patch.object(fr, "get_all_companies", _companies),
    ):
        with pytest.warns(Warning):
            with pytest.raises(OpenBBError, match="No frame was found"):
                asyncio.run(
                    fr.get_frame(fact="Revenues", year=2023, fiscal_period="q1")
                )


def test_get_frame_annual_failure_raises():
    """A non-quarter, non-instant request that fails raises OpenBBError."""

    async def _fetch(url, use_cache, persist):
        raise RuntimeError("no frame")

    async def _companies(use_cache=True):
        return _frame_companies()

    with (
        patch.object(fr, "fetch_data", _fetch),
        patch.object(fr, "get_all_companies", _companies),
    ):
        with pytest.raises(OpenBBError, match="No frame was found"):
            asyncio.run(fr.get_frame(fact="Revenues", year=2023))


_CONCEPT_RESP = {
    "cik": 320193,
    "taxonomy": "us-gaap",
    "tag": "Revenues",
    "label": "Revenues",
    "description": "d",
    "entityName": "Apple",
    "units": {
        "USD": [
            {
                "fy": 2023,
                "fp": "FY",
                "filed": "2024-01-01",
                "end": "2023-12-31",
                "val": 100,
            },
            {
                "fy": 2022,
                "fp": "FY",
                "filed": "2023-01-01",
                "end": "2022-12-31",
                "val": 90,
            },
        ]
    },
}


def test_get_concept_happy_path_with_year_filter():
    """get_concept attaches metadata, flattens units, and filters by year."""

    async def _symbol_map(ticker, *a, **k):
        return "0000320193"

    async def _fetch(url, use_cache, persist):
        return _CONCEPT_RESP

    with (
        patch.object(fr, "symbol_map", _symbol_map),
        patch.object(fr, "fetch_data", _fetch),
    ):
        res = asyncio.run(fr.get_concept("AAPL", fact="Revenues", year=2023))
    assert res["metadata"]["AAPL"]["units"] == "USD"  # single unit unwrapped
    assert len(res["data"]) == 1
    item = res["data"][0]
    assert item["symbol"] == "AAPL"
    assert item["unit"] == "USD"
    assert item["fact"] == "Revenues"
    assert item["name"] == "Apple"


def test_get_concept_year_filter_miss_returns_all():
    """A year with no matches warns and returns the full result set."""

    async def _symbol_map(ticker, *a, **k):
        return "0000320193"

    async def _fetch(url, use_cache, persist):
        return _CONCEPT_RESP

    with (
        patch.object(fr, "symbol_map", _symbol_map),
        patch.object(fr, "fetch_data", _fetch),
    ):
        with pytest.warns(Warning):
            res = asyncio.run(fr.get_concept("AAPL", fact="Revenues", year=1999))
    assert len(res["data"]) == 2  # falls back to all entries


def test_get_concept_multi_unit():
    """A concept disclosed in multiple units lists them all in metadata."""
    resp = {
        "cik": 1,
        "taxonomy": "us-gaap",
        "tag": "Revenues",
        "label": "Revenues",
        "entityName": "Foo",
        "units": {
            "USD": [
                {
                    "fy": 2023,
                    "fp": "FY",
                    "filed": "2024-01-01",
                    "end": "2023-12-31",
                    "val": 1,
                }
            ],
            "CAD": [
                {
                    "fy": 2023,
                    "fp": "FY",
                    "filed": "2024-01-01",
                    "end": "2023-12-31",
                    "val": 2,
                }
            ],
        },
    }

    async def _symbol_map(ticker, *a, **k):
        return "0000000001"

    async def _fetch(url, use_cache, persist):
        return resp

    with (
        patch.object(fr, "symbol_map", _symbol_map),
        patch.object(fr, "fetch_data", _fetch),
    ):
        res = asyncio.run(fr.get_concept("FOO"))
    assert set(res["metadata"]["FOO"]["units"]) == {"USD", "CAD"}
    assert len(res["data"]) == 2


def test_get_concept_no_cik_raises_empty():
    """A symbol with no CIK warns and ultimately raises EmptyDataError."""

    async def _symbol_map(ticker, *a, **k):
        return ""

    async def _fetch(url, use_cache, persist):
        return {}

    with (
        patch.object(fr, "symbol_map", _symbol_map),
        patch.object(fr, "fetch_data", _fetch),
    ):
        with pytest.warns(Warning):
            with pytest.raises(EmptyDataError):
                asyncio.run(fr.get_concept("BADSYM"))


def test_get_concept_fetch_error_warns_and_raises_empty():
    """A valid CIK whose fetch raises is caught, warned, and ends in EmptyDataError.

    Unlike the no-CIK case, this exercises the try/except around fetch_data: the
    symbol resolves, the request raises, the error message is warned and recorded,
    and with no response collected the function raises EmptyDataError.
    """

    async def _symbol_map(ticker, *a, **k):
        return "0000320193"

    async def _fetch(url, use_cache, persist):
        raise RuntimeError("frame fetch failed")

    with (
        patch.object(fr, "symbol_map", _symbol_map),
        patch.object(fr, "fetch_data", _fetch),
    ):
        with pytest.warns(Warning):
            with pytest.raises(EmptyDataError):
                asyncio.run(fr.get_concept("AAPL", fact="Revenues"))
