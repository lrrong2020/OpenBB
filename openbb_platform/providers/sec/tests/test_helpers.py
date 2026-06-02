"""Unit tests for ``openbb_sec.utils.helpers``.

These exercise the pure-ish parsing/helper functions directly with crafted
synthetic inputs and mocked transport, covering branches the fetcher/VCR suites
never reach.  No real HTTP is performed: any function that fetches has its
transport patched at the import site (``openbb_sec.utils.helpers.*``).
"""

import asyncio
from unittest.mock import patch

import pytest
from openbb_core.app.model.abstract.error import OpenBBError

from openbb_sec.utils import helpers


def test_sec_callback_text_fallback():
    """sec_callback returns plain text when Content-Type is neither json/html."""

    class _Resp:
        headers = {"Content-Type": "application/octet-stream"}

        async def json(self):
            return {"unused": True}

        async def text(self, encoding=None):
            return f"plain:{encoding}"

    out = asyncio.run(helpers.sec_callback(_Resp(), None))
    # Falls through to ``response.text()`` with no encoding argument.
    assert out == "plain:None"


def test_sec_callback_json_and_html():
    """sec_callback dispatches on the json and html content types."""

    class _Json:
        headers = {"Content-Type": "application/json; charset=utf-8"}

        async def json(self):
            return {"ok": 1}

        async def text(self, encoding=None):
            return "x"

    class _Html:
        headers = {"Content-Type": "text/html"}

        async def json(self):
            return {}

        async def text(self, encoding=None):
            return f"html:{encoding}"

    assert asyncio.run(helpers.sec_callback(_Json(), None)) == {"ok": 1}
    # HTML path decodes with latin-1.
    assert asyncio.run(helpers.sec_callback(_Html(), None)) == "html:latin-1"


def test_get_all_companies_invalid_response():
    """An empty/invalid response raises OpenBBError."""

    async def _fake(url, **kwargs):
        return None

    # helpers imports cached_request at module scope, so patch it there.
    with patch.object(helpers, "cached_request", _fake):
        with pytest.raises(OpenBBError, match="Empty or invalid"):
            asyncio.run(helpers.get_all_companies())


def test_get_all_companies_unexpected_columns():
    """A response whose row width != 3 raises a format error."""

    async def _fake(url, **kwargs):
        # Each entity must map to a dict; here only two fields per row.
        return {"0": {"cik_str": 320193, "ticker": "AAPL"}}

    with patch.object(helpers, "cached_request", _fake):
        with pytest.raises(OpenBBError, match="Unexpected SEC response format"):
            asyncio.run(helpers.get_all_companies())


def test_get_all_companies_ok():
    """A well-formed response yields a 3-column string DataFrame."""

    async def _fake(url, **kwargs):
        return {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
            "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft"},
        }

    with patch.object(helpers, "cached_request", _fake):
        df = asyncio.run(helpers.get_all_companies())
    assert list(df.columns) == ["cik", "symbol", "name"]
    assert df.loc["0", "symbol"] == "AAPL"
    assert df.loc["0", "cik"] == "320193"  # astype(str)


def _ciks_frame():
    """Patch get_all_ciks to a small institutions frame."""

    async def _fake(use_cache=True):
        from pandas import DataFrame

        return DataFrame(
            {
                "Institution": ["VANGUARD GROUP INC", "BLACKROCK INC", "ACME LLC"],
                "CIK Number": ["0000102909", "0001364742", "0000999999"],
            }
        )

    return _fake


def test_search_institutions_case_insensitive():
    """search_institutions filters by case-insensitive substring."""
    with patch.object(helpers, "get_all_ciks", _ciks_frame()):
        out = asyncio.run(helpers.search_institutions("blackrock"))
    assert len(out) == 1
    assert out.iloc[0]["CIK Number"] == "0001364742"


def _companies_frame():
    from pandas import DataFrame

    return DataFrame(
        {
            "cik": ["320193", "789019"],
            "symbol": ["AAPL", "MSFT"],
            "name": ["Apple Inc.", "Microsoft"],
        }
    )


def _mf_frame():
    from pandas import DataFrame

    return DataFrame(
        {
            "cik": ["36405"],
            "seriesId": ["S000002277"],
            "classId": ["C000005942"],
            "symbol": ["VFINX"],
        }
    )


def test_symbol_map_company_hit():
    """A ticker present in the company list zero-pads to a 10-digit CIK."""

    async def _companies(use_cache=True):
        return _companies_frame()

    with patch.object(helpers, "get_all_companies", _companies):
        cik = asyncio.run(helpers.symbol_map("aapl"))
    assert cik == "0000320193"


def test_symbol_map_fund_fallback():
    """A ticker absent from companies falls back to the MF/ETF map."""

    async def _companies(use_cache=True):
        return _companies_frame()

    async def _mf(use_cache=True):
        return _mf_frame()

    with patch.object(helpers, "get_all_companies", _companies), patch.object(
        helpers, "get_mf_and_etf_map", _mf
    ):
        cik = asyncio.run(helpers.symbol_map("VFINX"))
    assert cik == "0000036405"


def test_symbol_map_not_found_returns_empty():
    """A ticker in neither list returns an empty string."""

    async def _companies(use_cache=True):
        return _companies_frame()

    async def _mf(use_cache=True):
        return _mf_frame()

    with patch.object(helpers, "get_all_companies", _companies), patch.object(
        helpers, "get_mf_and_etf_map", _mf
    ):
        assert asyncio.run(helpers.symbol_map("NOPE")) == ""


def test_cik_map_hit_and_miss():
    """cik_map resolves an integer CIK to a ticker, else returns an error string."""

    async def _companies(use_cache=True):
        return _companies_frame()

    with patch.object(helpers, "get_all_companies", _companies):
        assert asyncio.run(helpers.cik_map(320193)) == "AAPL"
        # A string CIK with leading zeros that is not present hits the error branch.
        msg = asyncio.run(helpers.cik_map("0000000001"))
    assert "does not have a unique ticker" in msg


def test_get_schema_filelist():
    """get_schema_filelist parses the 'Name' column of an HTML table."""
    html = (
        "<table><tr><th>Name</th></tr>"
        "<tr><td>Parent Directory</td></tr>"
        "<tr><td>elts/</td></tr>"
        "<tr><td>us-gaap-2024.xsd</td></tr></table>"
    )
    with patch.object(helpers, "cached_text", return_value=html):
        out = helpers.get_schema_filelist(query="elts")
    # First entry is rewritten to the directory URL; rest are file names.
    assert out[0] == "https://xbrl.fasb.org/us-gaap/elts/"
    assert "us-gaap-2024.xsd" in out


def test_get_schema_filelist_explicit_url_no_query():
    """With an explicit url and no query the first cell becomes that url."""
    html = "<table><tr><th>Name</th></tr><tr><td>Parent Directory</td></tr><tr><td>a.xsd</td></tr></table>"
    with patch.object(helpers, "cached_text", return_value=html):
        out = helpers.get_schema_filelist(url="https://example.com/dir")
    assert out[0] == "https://example.com/dir"
    assert out[1] == "a.xsd"


def _ftd_zip_bytes(rows: str) -> bytes:
    """Build an in-memory pipe-delimited zip the way the SEC serves FTD data."""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ftd.txt", rows)
    return buf.getvalue()


def test_download_zip_file_zip_branch_and_settlement():
    """A real zip (read_csv ValueError) takes the ZipFile branch and renames cols.

    read_csv(BytesIO, compression='zip') succeeds for a single-member zip, so to
    force the ValueError->ZipFile fallback we hand back bytes that are a valid
    zip but whose direct csv read fails; a multi-line pipe file with a header is
    parsed, the last two summary rows trimmed, and SETTLEMENT DATE columns mapped.
    """
    # A non-numeric price token ("UNAVAILABLE") keeps PRICE as a string column so
    # the source's regex mask runs, converting the junk value to None then float.
    rows = (
        "SETTLEMENT DATE|CUSIP|SYMBOL|QUANTITY (FAILS)|DESCRIPTION|PRICE\n"
        "20230103|000000000|AAPL|100|APPLE INC|130.5\n"
        "20230103|000000001|MSFT|200|MICROSOFT|UNAVAILABLE\n"
        "summary line one\n"
        "summary line two\n"
    )
    zip_bytes = _ftd_zip_bytes(rows)

    async def _fake(url, **kwargs):
        return zip_bytes

    # Force the except-ValueError path by making the first read_csv raise.
    real_read_csv = __import__("pandas").read_csv
    calls = {"n": 0}

    def _read_csv(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1 and kwargs.get("compression") == "zip":
            raise ValueError("forced fallback")
        return real_read_csv(*args, **kwargs)

    with patch.object(helpers, "cached_request", _fake), patch(
        "pandas.read_csv", _read_csv
    ):
        out = asyncio.run(helpers.download_zip_file("http://x/ftd.zip", symbol="AAPL"))

    assert isinstance(out, list)
    assert len(out) == 1  # filtered to AAPL
    rec = out[0]
    assert rec["symbol"] == "AAPL"
    assert "cusip" in rec  # SETTLEMENT DATE columns renamed
    assert str(rec["date"]) == "2023-01-03"  # parsed %Y%m%d -> date
    assert rec["price"] == 130.5  # numeric price preserved through the mask


def test_download_zip_file_direct_read_branch():
    """A single-member zip is parsed directly by read_csv (the non-error branch).

    Unlike the ZipFile-fallback test, no ValueError is forced, so the
    ``read_csv(BytesIO, compression='zip')`` call succeeds and the summary rows
    are trimmed via ``iloc[:-2]``. A non-numeric PRICE token keeps that column as
    strings so the regex price mask still runs.
    """
    rows = (
        "SETTLEMENT DATE|CUSIP|SYMBOL|QUANTITY (FAILS)|DESCRIPTION|PRICE\n"
        "20230103|000000000|AAPL|100|APPLE INC|130.5\n"
        "20230104|000000001|MSFT|150|MICROSOFT|UNAVAILABLE\n"
        "summary one\n"
        "summary two\n"
    )
    zip_bytes = _ftd_zip_bytes(rows)

    async def _fake(url, **kwargs):
        return zip_bytes

    with patch.object(helpers, "cached_request", _fake):
        out = asyncio.run(helpers.download_zip_file("http://x/ftd.zip", symbol="AAPL"))

    assert len(out) == 1  # filtered to AAPL, summary rows trimmed
    rec = out[0]
    assert rec["symbol"] == "AAPL"
    assert "cusip" in rec
    assert str(rec["date"]) == "2023-01-03"
    assert rec["price"] == 130.5


def test_get_series_id_requires_input():
    """get_series_id raises when neither symbol nor cik is supplied."""
    with pytest.raises(OpenBBError, match="Either symbol or cik"):
        asyncio.run(helpers.get_series_id())


def test_get_nport_candidates_empty_frame_falls_back_to_symbol_map():
    """An empty (0-row) series-id frame trips ``len(_series_id) == 0`` and falls
    back to ``symbol_map``; an unknown symbol maps to ``""`` and raises not-found."""
    from pandas import DataFrame

    async def _series(symbol, use_cache=True):
        return DataFrame({"seriesId": []})

    async def _symbol_map(symbol, use_cache=True):
        return ""

    with patch.object(helpers, "get_series_id", _series), patch.object(
        helpers, "symbol_map", _symbol_map
    ):
        with pytest.raises(OpenBBError, match="Fund not found"):
            asyncio.run(helpers.get_nport_candidates("BADFUND"))


def test_get_nport_candidates_empty_series_raises():
    """A blank series id raises the fund-not-found error before any request."""

    async def _series(symbol, use_cache=True):
        return None

    async def _symbol_map(symbol, use_cache=True):
        return ""

    with patch.object(helpers, "get_series_id", _series), patch.object(
        helpers, "symbol_map", _symbol_map
    ):
        with pytest.raises(OpenBBError, match="Fund not found"):
            asyncio.run(helpers.get_nport_candidates("BADFUND"))
