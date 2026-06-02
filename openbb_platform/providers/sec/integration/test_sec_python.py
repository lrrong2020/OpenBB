"""Test SEC extension."""

import pytest
from openbb_core.app.model.obbject import OBBject


@pytest.fixture(scope="session")
def obb(pytestconfig):
    """Fixture to setup obb."""

    if pytestconfig.getoption("markexpr") != "not integration":
        import openbb

        return openbb.obb




@pytest.mark.parametrize(
    "params",
    [
        ({"symbol": "TSLA", "provider": "sec", "use_cache": None}),
        ({"symbol": "SQQQ", "provider": "sec", "use_cache": None}),
    ],
)
@pytest.mark.integration
def test_sec_cik_map(params, obb):
    """Test the SEC CIK map endpoint."""
    result = obb.sec.cik_map(**params)
    assert result
    assert isinstance(result, OBBject)
    assert hasattr(result.results, "cik")
    assert isinstance(result.results.cik, str)


@pytest.mark.parametrize(
    "params",
    [
        ({"query": "berkshire hathaway", "provider": "sec", "use_cache": None}),
    ],
)
@pytest.mark.integration
def test_sec_institutions_search(params, obb):
    """Test the SEC institutions search endpoint."""
    result = obb.sec.institutions_search(**params)
    assert result
    assert isinstance(result, OBBject)
    assert len(result.results) > 0


@pytest.mark.parametrize(
    "params",
    [
        ({"provider": "sec"}),
        (
            {
                "provider": "sec",
                "taxonomy": "us-gaap",
                "year": 2024,
                "component": "soi",
                "category": None,
            }
        ),
    ],
)
@pytest.mark.integration
def test_sec_schema_files(params, obb):
    """Test the SEC schema files endpoint."""
    result = obb.sec.schema_files(**params)
    assert result
    assert isinstance(result, OBBject)
    assert len(result.results) > 0


@pytest.mark.parametrize(
    "params",
    [
        ({"query": "0000909832", "provider": "sec", "use_cache": None}),
        ({"query": "0001067983", "provider": "sec", "use_cache": None}),
    ],
)
@pytest.mark.integration
def test_sec_symbol_map(params, obb):
    """Test the SEC symbol map endpoint."""
    result = obb.sec.symbol_map(**params)
    assert result
    assert isinstance(result, OBBject)
    assert hasattr(result.results, "symbol")
    assert isinstance(result.results.symbol, str)


@pytest.mark.parametrize(
    "params",
    [{"provider": "sec"}],
)
@pytest.mark.integration
def test_sec_rss_litigation(params, obb):
    """Test the SEC RSS litigation endpoint."""
    result = obb.sec.rss_litigation(**params)
    assert result
    assert isinstance(result, OBBject)
    assert len(result.results) > 0


@pytest.mark.parametrize(
    "params",
    [{"query": "oil", "use_cache": False, "provider": "sec"}],
)
@pytest.mark.integration
def test_sec_sic_search(params, obb):
    """Test the SEC SIC search endpoint."""
    result = obb.sec.sic_search(**params)
    assert result
    assert isinstance(result, OBBject)
    assert len(result.results) > 0


@pytest.mark.parametrize(
    "params",
    [
        (
            {
                "url": "https://www.sec.gov/Archives/edgar/data/21344/000155278124000634/",
                "provider": "sec",
                "use_cache": True,
            }
        ),
    ],
)
@pytest.mark.integration
def test_sec_filing_headers(params, obb):
    """Test the SEC Filing Headers endpoint."""
    from openbb_sec.models.sec_filing import SecFilingData

    result = obb.sec.filing_headers(**params)
    assert result
    assert isinstance(result, OBBject)
    assert isinstance(result.results, SecFilingData)
    assert hasattr(result.results, "cover_page")


@pytest.mark.parametrize(
    "params",
    [
        (
            {
                "url": "https://www.sec.gov/Archives/edgar/data/1990353/000110465925015513/tm256977d7_ex99-1.htm",
                "provider": "sec",
                "use_cache": True,
            }
        ),
    ],
)
@pytest.mark.integration
def test_sec_htm_file(params, obb):
    """Test the SEC HTM File endpoint."""
    from openbb_sec.models.htm_file import SecHtmFileData

    result = obb.sec.htm_file(**params)
    assert result
    assert isinstance(result, OBBject)
    assert isinstance(result.results, SecHtmFileData)
    assert hasattr(result.results, "content")
