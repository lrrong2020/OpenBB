"""Unit tests for ``openbb_sec.models.htm_file``."""

import pytest
from openbb_core.app.model.abstract.error import OpenBBError

from openbb_sec.models.htm_file import SecHtmFileData, SecHtmFileFetcher


def test_htm_file_transform_query_empty_url():
    """htm_file.py:44 -> raise on empty URL."""
    with pytest.raises(OpenBBError) as exc:
        SecHtmFileFetcher.transform_query({"url": ""})
    assert "enter a URL" in str(exc.value)


def test_htm_file_transform_query_invalid_url():
    """htm_file.py:53 -> raise on a non-SEC / non-htm URL."""
    with pytest.raises(OpenBBError) as exc:
        SecHtmFileFetcher.transform_query({"url": "https://example.com/file.pdf"})
    assert "Invalid URL" in str(exc.value)


def test_htm_file_transform_query_valid_url():
    """htm_file.py happy path: a valid SEC htm URL is accepted."""
    url = "https://www.sec.gov/Archives/edgar/data/320193/x.htm"
    query = SecHtmFileFetcher.transform_query({"url": url})
    assert query.url == url


def test_htm_file_transform_data_empty_content():
    """htm_file.py:84 -> raise OpenBBError when content is missing."""
    with pytest.raises(OpenBBError) as exc:
        SecHtmFileFetcher.transform_data(
            query=None, data={"url": "https://www.sec.gov/x.htm", "content": ""}
        )
    assert "Failed to extract HTM file data" in str(exc.value)


def test_htm_file_transform_data_strips_row_attrs():
    """htm_file.py:90-95 -> style/class/bgcolor stripped from table rows."""
    content = (
        "<html><body><table>"
        "<tr class='x' bgcolor='#fff' style='background-color:#fff'>"
        "<td>1</td></tr></table></body></html>"
    )
    result = SecHtmFileFetcher.transform_data(
        query=None,
        data={"url": "https://www.sec.gov/x.htm", "content": content},
    )
    assert isinstance(result, SecHtmFileData)
    assert "bgcolor" not in result.content
    assert "class=" not in result.content
    assert "background-color" not in result.content
    assert "<td>1</td>" in result.content
