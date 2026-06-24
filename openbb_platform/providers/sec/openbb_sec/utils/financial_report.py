"""Render a filing's SEC financial report (FilingSummary R-files) as one page.

EDGAR renders XBRL into per-statement ``R{n}.htm`` tables (listed in
``FilingSummary.xml``) styled by the filing's ``report.css``. This assembles
those into a single document — one ``<section>`` per report, the stylesheet
inlined — so the viewer's section menu can page through the as-filed statements
and notes with their native styling.
"""

import asyncio
import re
from html import escape

_REPORT_RE = re.compile(r"<Report\b.*?</Report>", re.S)
_HTML_FILE_RE = re.compile(r"<HtmlFileName>\s*([^<]+?)\s*</HtmlFileName>")
_SHORT_NAME_RE = re.compile(r"<ShortName>\s*([^<]*?)\s*</ShortName>")
_BODY_RE = re.compile(r"<body[^>]*>(.*?)</body>", re.S | re.I)
_HEAD_RE = re.compile(r"</head>(.*?)</html>", re.S | re.I)
_SCRIPT_RE = re.compile(r"(?is)<script\b[^>]*>.*?</script\s*>")

# EDGAR's canonical renderer assets; the R-files are authored against these.
_GLOBAL_CSS = "https://www.sec.gov/include/report.css"
_GLOBAL_JS = "https://www.sec.gov/include/Show.js"


async def _get(url: str, use_cache: bool) -> bytes:
    """Fetch raw bytes via the cached, rate-limited SEC client."""
    from openbb_sec.utils.cache import cached_bytes
    from openbb_sec.utils.definitions import SEC_HEADERS

    try:
        return await asyncio.to_thread(
            cached_bytes,
            url,
            use_cache=use_cache,
            headers=SEC_HEADERS,
            raise_for_status=False,
        )
    except Exception:  # noqa: BLE001
        return b""


def _extract_body(html: str) -> "str | None":
    """Return the inner body of an R-file, dropping its head/link/script."""
    match = _BODY_RE.search(html) or _HEAD_RE.search(html)
    return match.group(1) if match else None


def _collect_inline_scripts(html: str) -> str:
    """Concatenate the JS of inline (non-``src``) script tags — the row toggles."""
    out = []
    for match in _SCRIPT_RE.finditer(html):
        block = match.group(0)
        open_tag = block[: block.find(">") + 1]
        if "src=" in open_tag.lower():
            continue
        inner = block[block.find(">") + 1 : block.rfind("<")]
        if inner.strip():
            out.append(inner.strip())
    return "\n".join(out)


async def render_financial_report(
    directory: str, use_cache: bool = True
) -> "str | None":
    """Assemble a filing's R-file statements into one section-per-report page."""
    summary = (await _get(directory + "FilingSummary.xml", use_cache)).decode(
        "utf-8", "ignore"
    )
    if not summary:
        return None

    reports: list = []
    for block in _REPORT_RE.findall(summary):
        html_file = _HTML_FILE_RE.search(block)
        short_name = _SHORT_NAME_RE.search(block)
        if html_file and html_file.group(1).strip():
            name = (
                short_name.group(1).strip() if short_name else ""
            ) or html_file.group(1).strip()
            reports.append((name, html_file.group(1).strip()))
    if not reports:
        return None

    results = await asyncio.gather(
        *[_get(directory + html_file, use_cache) for _, html_file in reports],
        return_exceptions=True,
    )

    sections: list = []
    inline_js = ""
    for (name, _html_file), data in zip(reports, results):
        if isinstance(data, BaseException) or not data:
            continue
        html = data.decode("utf-8", "ignore")
        if not inline_js:
            inline_js = _collect_inline_scripts(html)
        body = _extract_body(html)
        if body and body.strip():
            # Drop the R-file's own scripts; the row-toggle JS is added once below.
            body = _SCRIPT_RE.sub("", body)
            sections.append(
                f'<section class=ob-sec data-name="{escape(name)}">{body}</section>'
            )
    if not sections:
        return None

    css = (await _get(_GLOBAL_CSS, use_cache)).decode("utf-8", "ignore")
    js = (await _get(_GLOBAL_JS, use_cache)).decode("utf-8", "ignore")
    style = f"<style>{css}</style>" if css else ""
    script = f"<script>{js}\n{inline_js}</script>" if (js or inline_js) else ""
    return f'{style}<div class="ob-fr">{script}{"".join(sections)}</div>'
