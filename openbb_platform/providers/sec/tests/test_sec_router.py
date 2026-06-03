"""Unit tests for the SEC router (``openbb_sec.sec_router``).

The router commands are otherwise only exercised by the live ``integration``
suite, so these tests cover registration and the command bodies without any
network access by mocking ``Query`` and ``OBBject.from_query``.

The SEC provider implements a number of standard models normally surfaced
through the ``openbb-equity`` and ``openbb-etf`` routers. When either extension
is not installed, those models are registered under SEC-prefixed names and
exposed through the SEC router instead. The fallback commands are therefore
registered conditionally, which the tests below account for.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openbb_sec import sec_router

# Commands that are always registered on the SEC router.
_BASE_COMMANDS = [
    "filing_headers",
    "htm_file",
    "cik_map",
    "institutions_search",
    "schema_files",
    "symbol_map",
    "rss_litigation",
    "sic_search",
]

# Registered on the SEC router only when ``openbb-equity`` is not installed.
_EQUITY_FALLBACK_COMMANDS = [
    "balance_sheet",
    "balance_sheet_growth",
    "cash_flow",
    "cash_flow_growth",
    "income_statement",
    "income_statement_growth",
    "company_filings",
    "compare_company_facts",
    "equity_search",
    "latest_financial_reports",
    "insider_trading",
    "form_13f",
    "equity_ftd",
    "management_discussion_analysis",
]

# Registered on the SEC router only when ``openbb-etf`` is not installed.
_ETF_FALLBACK_COMMANDS = ["nport_disclosure"]


def test_router_metadata():
    """The router uses an empty prefix and a SEC description."""
    assert sec_router.router.prefix == ""
    assert "SEC" in sec_router.router.description


def test_all_commands_registered():
    """The registered commands match the current install configuration.

    The base commands are always present; the equity/etf fallback commands are
    present only when the respective extension is absent.
    """
    paths = {route.path for route in sec_router.router.api_router.routes}
    expected = set(_BASE_COMMANDS)
    if not sec_router.EQUITY_INSTALLED:
        expected |= set(_EQUITY_FALLBACK_COMMANDS)
    if not sec_router.ETF_INSTALLED:
        expected |= set(_ETF_FALLBACK_COMMANDS)
    assert paths == {f"/{name}" for name in expected}


@pytest.mark.parametrize("command_name", _BASE_COMMANDS)
def test_command_delegates_to_from_query(command_name):
    """Each base command builds a Query and awaits OBBject.from_query."""
    sentinel = object()
    command = getattr(sec_router, command_name)
    with (
        patch.object(sec_router, "Query", MagicMock()) as mock_query,
        patch.object(
            sec_router.OBBject,
            "from_query",
            new=AsyncMock(return_value=sentinel),
        ) as mock_from_query,
    ):
        result = asyncio.run(
            command(
                cc=None,
                provider_choices=None,
                standard_params=None,
                extra_params=None,
            )
        )
    assert result is sentinel
    mock_query.assert_called_once()
    mock_from_query.assert_awaited_once()


def _load_standalone_router_module():
    """Re-execute ``sec_router`` with both install flags forced to False.

    Loaded under a private module name so the live ``openbb_sec.sec_router``
    used elsewhere in the suite is untouched. ``Router.command`` is replaced
    during load with a passthrough decorator so the fallback endpoints bind
    without requiring the SEC-prefixed models to be resolved through the live
    provider registry or FastAPI's response-model machinery.
    """
    import importlib.util
    from pathlib import Path

    from openbb_core.app.router import Router

    import openbb_sec

    spec = importlib.util.spec_from_file_location(
        "openbb_sec_sec_router_standalone",
        Path(openbb_sec.__file__).parent / "sec_router.py",
    )
    module = importlib.util.module_from_spec(spec)
    original_equity = openbb_sec.EQUITY_INSTALLED
    original_etf = openbb_sec.ETF_INSTALLED
    original_command = Router.command
    openbb_sec.EQUITY_INSTALLED = False
    openbb_sec.ETF_INSTALLED = False

    def _passthrough_command(self, func=None, **_kwargs):
        """Bind ``func`` without touching the underlying FastAPI router."""
        if func is None:
            return lambda f: _passthrough_command(self, f, **_kwargs)
        return func

    Router.command = _passthrough_command  # type: ignore[assignment]
    try:
        spec.loader.exec_module(module)
    finally:
        openbb_sec.EQUITY_INSTALLED = original_equity
        openbb_sec.ETF_INSTALLED = original_etf
        Router.command = original_command  # type: ignore[assignment]
    return module


class TestStandaloneFallbackEndpoints:
    """The commands registered only when ``openbb-equity``/``openbb-etf`` are absent."""

    _STANDALONE_NAMES = tuple(_EQUITY_FALLBACK_COMMANDS + _ETF_FALLBACK_COMMANDS)

    def test_standalone_module_binds_all_fallback_endpoint_names(self):
        """All fallback endpoint names exist as module attributes after reload."""
        module = _load_standalone_router_module()
        for name in self._STANDALONE_NAMES:
            assert callable(getattr(module, name, None)), f"missing {name}"

    def test_standalone_module_binds_base_endpoint_names(self):
        """The always-present base commands also bind in the standalone module."""
        module = _load_standalone_router_module()
        for name in _BASE_COMMANDS:
            assert callable(getattr(module, name, None)), f"missing {name}"

    @pytest.mark.parametrize("endpoint_name", _STANDALONE_NAMES)
    def test_standalone_endpoint_body_delegates_to_from_query(self, endpoint_name):
        """Each fallback endpoint body calls ``OBBject.from_query(Query(**locals()))``."""
        module = _load_standalone_router_module()
        fn = getattr(module, endpoint_name)

        sentinel = object()
        with (
            patch.object(module, "Query", new=MagicMock()) as mock_query,
            patch.object(
                module.OBBject,
                "from_query",
                new=AsyncMock(return_value=sentinel),
            ) as mock_from_query,
        ):
            out = asyncio.run(
                fn(
                    cc=MagicMock(),
                    provider_choices=MagicMock(),
                    standard_params=MagicMock(),
                    extra_params=MagicMock(),
                )
            )
        assert out is sentinel
        mock_query.assert_called_once()
        mock_from_query.assert_awaited_once()
