"""SEC Router."""

from openbb_core.app.model.command_context import CommandContext
from openbb_core.app.model.example import APIEx, PythonEx
from openbb_core.app.model.obbject import OBBject
from openbb_core.app.provider_interface import (
    ExtraParams,
    ProviderChoices,
    StandardParams,
)
from openbb_core.app.query import Query
from openbb_core.app.router import Router

router = Router(
    prefix="",
    description="U.S. Securities and Exchange Commission (SEC) public data.",
)


@router.command(
    model="SecFiling",
    examples=[
        APIEx(
            parameters={
                "url": "https://www.sec.gov/Archives/edgar/data/317540/000119312524076556/d645509ddef14a.htm",
                "provider": "sec",
            }
        )
    ],
    openapi_extra={
        "widget_config": {
            "description": "Get a list of all the documents associated with a filing, and their direct URLs.",
            "gridData": {
                "w": 30,
                "h": 10,
            },
            "refetchInterval": False,
            "data": {"dataKey": "results.document_urls"},
        }
    },
)
async def filing_headers(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Download the index headers, and cover page if available, for any SEC filing."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="SecHtmFile",
    examples=[
        APIEx(
            parameters={
                "url": "https://www.sec.gov/Archives/edgar/data/1723690/000119312525030074/d866336dex991.htm",
                "provider": "sec",
            }
        )
    ],
    openapi_extra={
        "widget_config": {
            "name": "Open HTML",
            "description": "Open a HTM/HTML document from the SEC website.",
            "gridData": {
                "w": 40,
                "h": 25,
            },
            "refetchInterval": False,
            "type": "markdown",
            "data": {
                "dataKey": "results.content",
            },
        }
    },
)
async def htm_file(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Download a raw HTML object from the SEC website."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="CikMap",
    examples=[APIEx(parameters={"symbol": "MSFT", "provider": "sec"})],
)
async def cik_map(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Map a ticker symbol to a CIK number."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="InstitutionsSearch",
    examples=[
        APIEx(parameters={"provider": "sec"}),
        APIEx(parameters={"query": "blackstone real estate", "provider": "sec"}),
    ],
)
async def institutions_search(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Search SEC-regulated institutions by name and return a list of results with CIK numbers."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="SchemaFiles",
    examples=[
        APIEx(parameters={"provider": "sec"}),
        PythonEx(
            description="Explore XBRL taxonomies progressively.",
            code=[
                "# List all available taxonomy families",
                "obb.sec.schema_files(provider='sec')",
                "# List components for US GAAP (latest year)",
                "obb.sec.schema_files(taxonomy='us-gaap', provider='sec')",
                "# List presentation components for US GAAP 2024",
                "obb.sec.schema_files(taxonomy='us-gaap', year=2024, provider='sec')",
                "# Get the Statement of Income presentation structure",
                "obb.sec.schema_files(taxonomy='us-gaap', year=2024, component='soi', provider='sec')",
            ],
        ),
    ],
)
async def schema_files(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Explore SEC and FASB XBRL taxonomy schemas, labels, and presentation structures.

    - No parameters: list all available taxonomy families.
    - taxonomy only: get all parsed structures for the most recent year.
    - taxonomy + year: get all parsed structures for a specific year.
    - taxonomy + component: get one component's structure using the most recent year.
    - taxonomy + year + component: get one component's parsed structure.
    """
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="SymbolMap",
    examples=[APIEx(parameters={"query": "0000789019", "provider": "sec"})],
)
async def symbol_map(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Map a CIK number to a ticker symbol, leading 0s can be omitted or included."""
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="RssLitigation",
    examples=[APIEx(parameters={"provider": "sec"})],
)
async def rss_litigation(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Get the RSS feed that provides links to litigation releases concerning civil lawsuits brought by the Commission in federal court."""  # noqa: E501
    return await OBBject.from_query(Query(**locals()))


@router.command(
    model="SicSearch",
    examples=[
        APIEx(parameters={"provider": "sec"}),
        APIEx(parameters={"query": "real estate investment trusts", "provider": "sec"}),
    ],
)
async def sic_search(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Search for Industry Titles, Reporting Office, and SIC Codes. An empty query string returns all results."""
    return await OBBject.from_query(Query(**locals()))


# The SEC provider implements a number of standard models that are normally
# surfaced through the ``openbb-equity`` and ``openbb-etf`` routers. When either
# extension is not installed, those models are registered under SEC-prefixed
# names (see ``openbb_sec.__init__``) and exposed through this router instead.
from openbb_sec import EQUITY_INSTALLED, ETF_INSTALLED  # noqa: E402

if not EQUITY_INSTALLED:

    @router.command(
        model="SecBalanceSheet",
        examples=[
            APIEx(parameters={"symbol": "AAPL", "provider": "sec"}),
            APIEx(
                parameters={
                    "symbol": "AAPL",
                    "period": "annual",
                    "limit": 5,
                    "provider": "sec",
                }
            ),
        ],
    )
    async def balance_sheet(
        cc: CommandContext,
        provider_choices: ProviderChoices,
        standard_params: StandardParams,
        extra_params: ExtraParams,
    ) -> OBBject:
        """Get the balance sheet for a given company."""
        return await OBBject.from_query(Query(**locals()))

    @router.command(
        model="SecBalanceSheetGrowth",
        examples=[
            APIEx(parameters={"symbol": "AAPL", "provider": "sec"}),
            APIEx(parameters={"symbol": "AAPL", "limit": 10, "provider": "sec"}),
        ],
    )
    async def balance_sheet_growth(
        cc: CommandContext,
        provider_choices: ProviderChoices,
        standard_params: StandardParams,
        extra_params: ExtraParams,
    ) -> OBBject:
        """Get the growth of a company's balance sheet items over time."""
        return await OBBject.from_query(Query(**locals()))

    @router.command(
        model="SecCashFlowStatement",
        examples=[
            APIEx(parameters={"symbol": "AAPL", "provider": "sec"}),
            APIEx(
                parameters={
                    "symbol": "AAPL",
                    "period": "annual",
                    "limit": 5,
                    "provider": "sec",
                }
            ),
        ],
    )
    async def cash_flow(
        cc: CommandContext,
        provider_choices: ProviderChoices,
        standard_params: StandardParams,
        extra_params: ExtraParams,
    ) -> OBBject:
        """Get the cash flow statement for a given company."""
        return await OBBject.from_query(Query(**locals()))

    @router.command(
        model="SecCashFlowStatementGrowth",
        examples=[
            APIEx(parameters={"symbol": "AAPL", "provider": "sec"}),
            APIEx(parameters={"symbol": "AAPL", "limit": 10, "provider": "sec"}),
        ],
    )
    async def cash_flow_growth(
        cc: CommandContext,
        provider_choices: ProviderChoices,
        standard_params: StandardParams,
        extra_params: ExtraParams,
    ) -> OBBject:
        """Get the growth of a company's cash flow statement items over time."""
        return await OBBject.from_query(Query(**locals()))

    @router.command(
        model="SecIncomeStatement",
        examples=[
            APIEx(parameters={"symbol": "AAPL", "provider": "sec"}),
            APIEx(
                parameters={
                    "symbol": "AAPL",
                    "period": "annual",
                    "limit": 5,
                    "provider": "sec",
                }
            ),
        ],
    )
    async def income_statement(
        cc: CommandContext,
        provider_choices: ProviderChoices,
        standard_params: StandardParams,
        extra_params: ExtraParams,
    ) -> OBBject:
        """Get the income statement for a given company."""
        return await OBBject.from_query(Query(**locals()))

    @router.command(
        model="SecIncomeStatementGrowth",
        examples=[
            APIEx(parameters={"symbol": "AAPL", "provider": "sec"}),
            APIEx(
                parameters={
                    "symbol": "AAPL",
                    "limit": 10,
                    "period": "annual",
                    "provider": "sec",
                }
            ),
        ],
    )
    async def income_statement_growth(
        cc: CommandContext,
        provider_choices: ProviderChoices,
        standard_params: StandardParams,
        extra_params: ExtraParams,
    ) -> OBBject:
        """Get the growth of a company's income statement items over time."""
        return await OBBject.from_query(Query(**locals()))

    @router.command(
        model="SecCompanyFilings",
        examples=[
            APIEx(parameters={"symbol": "AAPL", "provider": "sec"}),
            APIEx(parameters={"limit": 100, "provider": "sec"}),
        ],
    )
    async def company_filings(
        cc: CommandContext,
        provider_choices: ProviderChoices,
        standard_params: StandardParams,
        extra_params: ExtraParams,
    ) -> OBBject:
        """Get public company filings."""
        return await OBBject.from_query(Query(**locals()))

    @router.command(
        model="SecCompareCompanyFacts",
        examples=[
            APIEx(parameters={"provider": "sec"}),
            APIEx(
                parameters={
                    "provider": "sec",
                    "fact": "PaymentsForRepurchaseOfCommonStock",
                    "year": 2023,
                }
            ),
            APIEx(
                parameters={
                    "provider": "sec",
                    "symbol": "NVDA,AAPL,AMZN,MSFT,GOOG,SMCI",
                    "fact": "RevenueFromContractWithCustomerExcludingAssessedTax",
                    "year": 2024,
                }
            ),
        ],
    )
    async def compare_company_facts(
        cc: CommandContext,
        provider_choices: ProviderChoices,
        standard_params: StandardParams,
        extra_params: ExtraParams,
    ) -> OBBject:
        """Compare reported company facts and fundamental data points."""
        return await OBBject.from_query(Query(**locals()))

    @router.command(
        model="SecEquitySearch",
        examples=[
            APIEx(parameters={"provider": "sec"}),
            APIEx(parameters={"query": "AAPL", "provider": "sec"}),
        ],
    )
    async def equity_search(
        cc: CommandContext,
        provider_choices: ProviderChoices,
        standard_params: StandardParams,
        extra_params: ExtraParams,
    ) -> OBBject:
        """Search for stock symbol, CIK, LEI, or company name."""
        return await OBBject.from_query(Query(**locals()))

    @router.command(
        model="SecLatestFinancialReports",
        examples=[
            APIEx(parameters={"provider": "sec"}),
            APIEx(parameters={"provider": "sec", "date": "2024-09-30"}),
        ],
    )
    async def latest_financial_reports(
        cc: CommandContext,
        provider_choices: ProviderChoices,
        standard_params: StandardParams,
        extra_params: ExtraParams,
    ) -> OBBject:
        """Get the newest quarterly, annual, and current reports for all companies."""
        return await OBBject.from_query(Query(**locals()))

    @router.command(
        model="SecInsiderTrading",
        examples=[
            APIEx(parameters={"symbol": "AAPL", "provider": "sec"}),
        ],
    )
    async def insider_trading(
        cc: CommandContext,
        provider_choices: ProviderChoices,
        standard_params: StandardParams,
        extra_params: ExtraParams,
    ) -> OBBject:
        """Get data about trading by a company's management team and board of directors."""
        return await OBBject.from_query(Query(**locals()))

    @router.command(
        model="SecForm13FHR",
        examples=[
            APIEx(parameters={"symbol": "NVDA", "provider": "sec"}),
            APIEx(
                description="Enter a date (calendar quarter ending) for a specific report.",
                parameters={"symbol": "BRK-A", "date": "2016-09-30", "provider": "sec"},
            ),
        ],
    )
    async def form_13f(
        cc: CommandContext,
        provider_choices: ProviderChoices,
        standard_params: StandardParams,
        extra_params: ExtraParams,
    ) -> OBBject:
        """Get the form 13F.

        The Securities and Exchange Commission's (SEC) Form 13F is a quarterly
        report that is required to be filed by all institutional investment
        managers with at least $100 million in assets under management.
        Managers are required to file Form 13F within 45 days after the last
        day of the calendar quarter. Most funds wait until the end of this
        period in order to conceal their investment strategy from competitors
        and the public.
        """
        return await OBBject.from_query(Query(**locals()))

    @router.command(
        model="SecEquityFtd",
        examples=[APIEx(parameters={"symbol": "AAPL", "provider": "sec"})],
    )
    async def equity_ftd(
        cc: CommandContext,
        provider_choices: ProviderChoices,
        standard_params: StandardParams,
        extra_params: ExtraParams,
    ) -> OBBject:
        """Get reported Fail-to-deliver (FTD) data."""
        return await OBBject.from_query(Query(**locals()))

    @router.command(
        model="SecManagementDiscussionAnalysis",
        examples=[
            APIEx(parameters={"symbol": "AAPL", "provider": "sec"}),
            APIEx(
                description="Get the Management Discussion & Analysis section by calendar year and period.",
                parameters={
                    "symbol": "AAPL",
                    "calendar_year": 2020,
                    "calendar_period": "Q4",
                    "provider": "sec",
                },
            ),
            APIEx(
                description="Setting 'include_tables' to True will attempt to extract all tables in valid Markdown.",
                parameters={
                    "symbol": "AAPL",
                    "calendar_year": 2020,
                    "calendar_period": "Q4",
                    "provider": "sec",
                    "include_tables": True,
                },
            ),
            APIEx(
                description="Setting 'raw_html' to True will bypass extraction and return the raw HTML file, as is."
                + " Use this for custom parsing or to access the entire HTML filing.",
                parameters={
                    "symbol": "AAPL",
                    "calendar_year": 2020,
                    "calendar_period": "Q4",
                    "provider": "sec",
                    "raw_html": True,
                },
            ),
        ],
        openapi_extra={
            "widget_config": {
                "type": "markdown",
                "data": {"dataKey": "results.content", "columnsDefs": []},
                "staleTime": 86400000,
                "refetchInterval": 86400000,
                "source": "SEC",
            }
        },
    )
    async def management_discussion_analysis(
        cc: CommandContext,
        provider_choices: ProviderChoices,
        standard_params: StandardParams,
        extra_params: ExtraParams,
    ) -> OBBject:
        """Get the Management Discussion & Analysis section from the financial statements for a given company."""
        return await OBBject.from_query(Query(**locals()))


if not ETF_INSTALLED:

    @router.command(
        model="SecNportDisclosure",
        examples=[
            APIEx(
                parameters={
                    "symbol": "XLK",
                    "provider": "sec",
                    "year": 2025,
                    "quarter": 1,
                }
            ),
        ],
    )
    async def nport_disclosure(
        cc: CommandContext,
        provider_choices: ProviderChoices,
        standard_params: StandardParams,
        extra_params: ExtraParams,
    ) -> OBBject:
        """Get SEC NPORT-P disclosure filings for a given ETF or mutual fund (US only)."""
        return await OBBject.from_query(Query(**locals()))
