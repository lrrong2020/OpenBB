"""Unit tests for ``openbb_sec.models.rss_litigation``."""

import types
from unittest.mock import patch

import pytest
from openbb_core.app.model.abstract.error import OpenBBError

from openbb_sec.models.rss_litigation import SecRssLitigationFetcher


def test_rss_litigation_extract_bad_status():
    """rss_litigation.py:66 -> raise OpenBBError on non-200 status code."""
    fake_response = types.SimpleNamespace(status_code=503, text="")
    query = SecRssLitigationFetcher.transform_query({})
    with patch(
        "openbb_core.provider.utils.helpers.make_request",
        return_value=fake_response,
    ):
        with pytest.raises(OpenBBError) as exc:
            SecRssLitigationFetcher.extract_data(query, None)
    assert "503" in str(exc.value)
