"""Unit tests for the SEC router (``openbb_sec.sec_router``).

The router commands are otherwise only exercised by the live ``integration``
suite, so these tests cover registration and the command bodies without any
network access by mocking ``Query`` and ``OBBject.from_query``.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openbb_sec import sec_router

_COMMANDS = [
    "filing_headers",
    "htm_file",
    "cik_map",
    "institutions_search",
    "schema_files",
    "symbol_map",
    "rss_litigation",
    "sic_search",
]


def test_router_metadata():
    """The router uses an empty prefix and a SEC description."""
    assert sec_router.router.prefix == ""
    assert "SEC" in sec_router.router.description


def test_all_commands_registered():
    """All eight SEC commands are registered on the router."""
    paths = {route.path for route in sec_router.router.api_router.routes}
    assert paths == {f"/{name}" for name in _COMMANDS}


@pytest.mark.parametrize("command_name", _COMMANDS)
def test_command_delegates_to_from_query(command_name):
    """Each command builds a Query and awaits OBBject.from_query."""
    sentinel = object()
    command = getattr(sec_router, command_name)
    with patch.object(sec_router, "Query", MagicMock()) as mock_query, patch.object(
        sec_router.OBBject,
        "from_query",
        new=AsyncMock(return_value=sentinel),
    ) as mock_from_query:
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
