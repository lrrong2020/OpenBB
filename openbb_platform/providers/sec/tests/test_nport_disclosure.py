"""Unit tests for ``openbb_sec.models.nport_disclosure``."""

import asyncio
import types
from datetime import date

import pytest
from openbb_core.app.model.abstract.error import OpenBBError
from openbb_core.provider.utils.errors import EmptyDataError

from openbb_sec.models.nport_disclosure import SecNportDisclosureFetcher


def _run(coro):
    """Run an async coroutine from a sync test (no pytest-asyncio)."""
    return asyncio.run(coro)


def _async_return(value):
    """Build a zero-arg awaitable returning ``value``."""

    async def _inner(*args, **kwargs):
        return value

    return _inner


def _wrap_nport(invst_records, fund_info=None, gen_info=None):
    """Wrap holding records in an NPORT-P submission envelope."""
    form_data = {"invstOrSecs": {"invstOrSec": invst_records}}
    if gen_info is not None:
        form_data["genInfo"] = gen_info
    if fund_info is not None:
        form_data["fundInfo"] = fund_info
    return {
        "edgarSubmission": {
            "headerData": {"submissionType": "NPORT-P"},
            "formData": form_data,
        }
    }


def _transform_nport(response):
    q = types.SimpleNamespace(symbol="TEST")
    return SecNportDisclosureFetcher.transform_data(q, response)


class TestNportQuery:
    """Query transform."""

    def test_transform_query(self):
        qp = SecNportDisclosureFetcher.transform_query({"symbol": "DIA"})
        assert qp.symbol == "DIA"
        assert qp.use_cache is True


_NPORT_XML = (
    b"<edgarSubmission><headerData>"
    b"<submissionType>NPORT-P</submissionType></headerData>"
    b"<formData></formData></edgarSubmission>"
)


def _nport_candidates():
    return [
        {
            "name": "Fund",
            "cik": "1",
            "file_date": "2025-04-01",
            "period_ending": "2025-03-31",
            "form_type": "NPORT-P",
            "primary_doc": "https://sec.gov/a.xml",
        },
        {
            "name": "Fund",
            "cik": "1",
            "file_date": "2025-01-01",
            "period_ending": "2024-12-31",
            "form_type": "NPORT-P",
            "primary_doc": "https://sec.gov/b.xml",
        },
    ]


class TestNportExtract:
    """aextract_data branches with patched candidate lookup + request."""

    def test_no_candidates_raises(self, monkeypatch):
        monkeypatch.setattr(
            "openbb_sec.utils.helpers.get_nport_candidates", _async_return([])
        )
        from openbb_sec.models.nport_disclosure import (
            SecNportDisclosureQueryParams,
        )

        q = SecNportDisclosureQueryParams(symbol="ZZZ", use_cache=False)
        with pytest.raises(OpenBBError, match="No N-Port records found"):
            _run(SecNportDisclosureFetcher.aextract_data(q, None))

    def test_latest_filing_when_no_year(self, monkeypatch):
        captured = {}

        async def fake_cached(url, **kwargs):
            captured["url"] = url
            return _NPORT_XML

        monkeypatch.setattr(
            "openbb_sec.utils.helpers.get_nport_candidates",
            _async_return(_nport_candidates()),
        )
        monkeypatch.setattr(
            "openbb_sec.utils.cache.cached_request", fake_cached
        )
        from openbb_sec.models.nport_disclosure import (
            SecNportDisclosureQueryParams,
        )

        q = SecNportDisclosureQueryParams(symbol="DIA", use_cache=False)
        out = _run(SecNportDisclosureFetcher.aextract_data(q, None))
        # No year/quarter -> first (most recent) candidate doc is fetched.
        assert captured["url"] == "https://sec.gov/a.xml"
        assert out["edgarSubmission"]["headerData"]["submissionType"] == "NPORT-P"

    def test_candidate_lookup_retries_after_error(self, monkeypatch):
        state = {"n": 0}

        async def flaky(symbol, use_cache=True):
            state["n"] += 1
            if state["n"] == 1:
                raise RuntimeError("RemoteDisconnected")
            return _nport_candidates()

        async def fake_cached(url, **kwargs):
            return _NPORT_XML

        # Skip the 1s backoff between retries.
        async def no_sleep(*args, **kwargs):
            return None

        monkeypatch.setattr(
            "openbb_sec.utils.helpers.get_nport_candidates", flaky
        )
        monkeypatch.setattr(
            "openbb_sec.utils.cache.cached_request", fake_cached
        )
        monkeypatch.setattr("asyncio.sleep", no_sleep)
        from openbb_sec.models.nport_disclosure import (
            SecNportDisclosureQueryParams,
        )

        q = SecNportDisclosureQueryParams(symbol="DIA", use_cache=False)
        with pytest.warns(Warning, match="Retrying"):
            out = _run(SecNportDisclosureFetcher.aextract_data(q, None))
        assert state["n"] == 2
        assert "edgarSubmission" in out

    def test_candidate_lookup_retries_exhausted_reraises(self, monkeypatch):
        # Every attempt fails -> the two interim failures warn-and-retry, and
        # after the final attempt the original error is re-raised (line 270).
        state = {"n": 0}

        async def always_fail(symbol, use_cache=True):
            state["n"] += 1
            raise RuntimeError("RemoteDisconnected")

        async def no_sleep(*args, **kwargs):
            return None

        monkeypatch.setattr(
            "openbb_sec.utils.helpers.get_nport_candidates", always_fail
        )
        monkeypatch.setattr("asyncio.sleep", no_sleep)
        from openbb_sec.models.nport_disclosure import (
            SecNportDisclosureQueryParams,
        )

        q = SecNportDisclosureQueryParams(symbol="DIA", use_cache=False)
        with pytest.warns(Warning, match="Retrying"):
            with pytest.raises(RuntimeError, match="RemoteDisconnected"):
                _run(SecNportDisclosureFetcher.aextract_data(q, None))
        # 3 attempts total: 2 warned retries + the final re-raise.
        assert state["n"] == 3

    def test_year_quarter_nearest_date(self, monkeypatch):
        captured = {}

        async def fake_cached(url, **kwargs):
            captured["url"] = url
            return _NPORT_XML

        monkeypatch.setattr(
            "openbb_sec.utils.helpers.get_nport_candidates",
            _async_return(_nport_candidates()),
        )
        monkeypatch.setattr(
            "openbb_sec.utils.cache.cached_request", fake_cached
        )
        from openbb_sec.models.nport_disclosure import (
            SecNportDisclosureQueryParams,
        )

        # 2025-Q1 quarter-end matches the 2025-03-31 candidate exactly.
        q = SecNportDisclosureQueryParams(
            symbol="DIA", year=2025, quarter=1, use_cache=False
        )
        out = _run(SecNportDisclosureFetcher.aextract_data(q, None))
        assert captured["url"] == "https://sec.gov/a.xml"
        assert "edgarSubmission" in out

    def test_year_only_infers_quarter_from_string_dates(self, monkeypatch):
        # year supplied without quarter -> the quarter is inferred from the
        # candidate ``period_ending`` values, which arrive as strings. Computing
        # ``max(dates).year`` on raw strings raised AttributeError, so the dates
        # must be coerced to datetimes before reading ``.year``.
        async def fake_cached(url, **kwargs):
            return _NPORT_XML

        monkeypatch.setattr(
            "openbb_sec.utils.helpers.get_nport_candidates",
            _async_return(_nport_candidates()),
        )
        monkeypatch.setattr("openbb_sec.utils.cache.cached_request", fake_cached)
        from openbb_sec.models.nport_disclosure import (
            SecNportDisclosureQueryParams,
        )

        q = SecNportDisclosureQueryParams(symbol="DIA", year=2025, use_cache=False)
        out = _run(SecNportDisclosureFetcher.aextract_data(q, None))
        # 2025 == latest candidate year -> Q1 inferred; a.xml (2025-03-31) chosen.
        assert "edgarSubmission" in out


class TestNportTransformDataGuards:
    """Top-level guards in transform_data."""

    def test_empty_data_raises(self):
        with pytest.raises(EmptyDataError):
            SecNportDisclosureFetcher.transform_data(
                types.SimpleNamespace(symbol="X"), {}
            )

    def test_non_nport_payload_returns_empty_result(self):
        # No holdings parsed, no metadata -> empty result, empty metadata.
        response = {
            "edgarSubmission": {
                "headerData": {"submissionType": "NPORT-P"},
                "formData": {},
            }
        }
        res = _transform_nport(response)
        assert res.result == []
        assert res.metadata == {}


class TestNportHoldings:
    """Holdings/derivatives parsing (the big transform_data block)."""

    def test_debt_security_with_lending_and_conditionals(self):
        debt = {
            "name": "DebtHld",
            "pctVal": "5.0",
            "valUSD": "1000",
            "curCd": "USD",
            "identifiers": {
                "isin": {"@value": "US0000000001"},
                "other": {"@value": "OTHERID"},
            },
            "securityLending": {
                "loanByFundCondition": {"@isLoanByFund": "Y", "@loanVal": "5"},
                "isCashCollateral": "N",
                "isNonCashCollateral": "N",
            },
            "debtSec": {
                "maturityDt": "2030-01-01",
                "couponKind": "Fixed",
                "annualizedRt": "3.5",
                "isDefault": "N",
                "areIntrstPmntsInArrs": "N",
                "isPaidKind": "N",
            },
            "issuerConditional": {"@desc": "issuer-desc"},
            "assetConditional": {"@desc": "asset-desc"},
            "currencyConditional": {"@curCd": "EUR", "@exchangeRt": "1.1"},
        }
        row = _transform_nport(_wrap_nport([debt])).result[0]
        d = row.model_dump(exclude_none=True)
        assert d["isin"] == "US0000000001"
        assert d["other_id"] == "OTHERID"
        assert d["is_loan_by_fund"] == "Y"
        assert d["loan_value"] == 5.0
        assert d["issuer_conditional"] == "issuer-desc"
        assert d["asset_conditional"] == "asset-desc"
        assert d["maturity_date"] == date(2030, 1, 1)
        assert d["coupon_kind"] == "Fixed"
        # annualized_return normalized to a fraction
        assert d["annualized_return"] == pytest.approx(0.035)
        assert d["exchange_currency"] == "EUR"
        assert d["exchange_rate"] == 1.1
        # weight normalized
        assert d["weight"] == pytest.approx(0.05)

    def test_option_derivative(self):
        opt = {
            "name": "OptHld",
            "pctVal": "2.0",
            "valUSD": "200",
            "identifiers": {},
            "derivativeInfo": {
                "optionSwaptionWarrantDeriv": {
                    "@derivCat": "OPT",
                    "counterparties": {
                        "counterpartyName": "CP1",
                        "counterpartyLei": "LEI1",
                    },
                    "descRefInstrmnt": {
                        "otherRefInst": {"issueTitle": "UnderTitle"}
                    },
                    "putOrCall": "Call",
                    "writtenOrPur": "Pur",
                    "expDt": "2025-12-31",
                    "exercisePrice": "10",
                    "exercisePriceCurCd": "USD",
                    "shareNo": "100",
                    "delta": "XXXX",
                    "unrealizedAppr": "12.5",
                }
            },
        }
        d = _transform_nport(_wrap_nport([opt])).result[0].model_dump(
            exclude_none=True
        )
        assert d["derivative_category"] == "OPT"
        assert d["counterparty"] == "CP1"
        assert d["lei"] == "LEI1"
        assert d["underlying_name"] == "UnderTitle"
        assert d["option_type"] == "Call"
        assert d["payoff_profile"] == "Pur"
        assert d["expiry_date"] == date(2025, 12, 31)
        assert d["exercise_price"] == 10.0
        assert d["exercise_currency"] == "USD"
        assert d["shares_per_contract"] == 100.0
        # delta == "XXXX" sentinel is skipped
        assert "delta" not in d
        assert d["unrealized_gain"] == 12.5

    def test_future_derivative(self):
        fut = {
            "name": "FutHld",
            "pctVal": "1.0",
            "valUSD": "100",
            "identifiers": {},
            "derivativeInfo": {
                "futrDeriv": {
                    "@derivCat": "FUT",
                    "counterparties": {
                        "counterpartyName": "CP2",
                        "counterpartyLei": "LEI2",
                    },
                    "descRefInstrmnt": {
                        "indexBasketInfo": {
                            "indexName": "SPX",
                            "indexIdentifier": "IDIDX",
                        }
                    },
                    "payOffProf": "Long",
                    "expDate": "2026-03-31",
                    "notionalAmt": "5000",
                    "curCd": "USD",
                    "unrealizedAppr": "20",
                }
            },
        }
        d = _transform_nport(_wrap_nport([fut])).result[0].model_dump(
            exclude_none=True
        )
        assert d["derivative_category"] == "FUT"
        assert d["counterparty"] == "CP2"
        assert d["underlying_name"] == "SPX"
        assert d["other_id"] == "IDIDX"
        assert d["payoff_profile"] == "Long"
        # expDate fallback used when expDt absent
        assert d["expiry_date"] == date(2026, 3, 31)
        assert d["notional_amount"] == 5000.0
        assert d["notional_currency"] == "USD"
        assert d["unrealized_gain"] == 20.0

    def test_forward_derivative(self):
        fwd = {
            "name": "FwdHld",
            "pctVal": "0.5",
            "valUSD": "50",
            "identifiers": {},
            "derivativeInfo": {
                "fwdDeriv": {
                    "@derivCat": "FWD",
                    "counterparties": {"counterpartyName": "CP3"},
                    "curSold": "USD",
                    "amtCurSold": "1000",
                    "curPur": "EUR",
                    "amtCurPur": "900",
                    "settlementDt": "2025-06-30",
                    "unrealizedAppr": "5",
                }
            },
        }
        d = _transform_nport(_wrap_nport([fwd])).result[0].model_dump(
            exclude_none=True
        )
        assert d["derivative_category"] == "FWD"
        assert d["counterparty"] == "CP3"
        assert d["currency_sold"] == "USD"
        assert d["currency_amount_sold"] == 1000.0
        assert d["currency_bought"] == "EUR"
        assert d["currency_amount_bought"] == 900.0
        assert d["expiry_date"] == date(2025, 6, 30)
        assert d["unrealized_gain"] == 5.0

    def test_swap_derivative(self):
        swap = {
            "name": "SwapHld",
            "pctVal": "0.25",
            "valUSD": "25",
            "identifiers": {},
            "derivativeInfo": {
                "swapDeriv": {
                    "@derivCat": "SWP",
                    "counterparties": {
                        "counterpartyName": "CP4",
                        "counterpartyLei": "LEI4",
                    },
                    "descRefInstrmnt": {
                        "indexBasketInfo": {
                            "indexName": "IDX",
                            "indexIdentifier": "IDID",
                        }
                    },
                    "floatingRecDesc": {
                        "@fixedOrFloating": "Floating",
                        "@floatingRtIndex": "LIBOR",
                        "@floatingRtSpread": "0.5",
                        "@pmntAmt": "100",
                        "rtResetTenors": {
                            "rtResetTenor": {
                                "@rateTenor": "M",
                                "@rateTenorUnit": "1",
                                "@resetDt": "D",
                                "@resetDtUnit": "1",
                            }
                        },
                    },
                    "floatingPmntDesc": {
                        "@fixedOrFloating": "Fixed",
                        "@floatingRtIndex": "SOFR",
                        "@floatingRtSpread": "0.25",
                        "@pmntAmt": "50",
                        "rtResetTenors": {
                            "rtResetTenor": {
                                "@rateTenor": "M",
                                "@rateTenorUnit": "3",
                                "@resetDt": "D",
                                "@resetDtUnit": "3",
                            }
                        },
                    },
                    "terminationDt": "2027-01-01",
                    "upfrontPmnt": "10",
                    "pmntCurCd": "USD",
                    "upfrontRcpt": "8",
                    "rcptCurCd": "EUR",
                    "notionalAmt": "2000",
                    "curCd": "USD",
                    "unrealizedAppr": "3",
                }
            },
        }
        d = _transform_nport(_wrap_nport([swap])).result[0].model_dump(
            exclude_none=True
        )
        assert d["derivative_category"] == "SWP"
        assert d["counterparty"] == "CP4"
        assert d["underlying_name"] == "IDX"
        assert d["other_id"] == "IDID"
        assert d["rate_type_rec"] == "Floating"
        assert d["floating_rate_index_rec"] == "LIBOR"
        assert d["floating_rate_spread_rec"] == 0.5
        assert d["rate_tenor_rec"] == "M"
        assert d["rate_type_pmnt"] == "Fixed"
        assert d["floating_rate_index_pmnt"] == "SOFR"
        assert d["receive_currency"] == "EUR"
        assert d["payment_currency"] == "USD"
        assert d["upfront_payment"] == 10.0
        assert d["upfront_receive"] == 8.0
        assert d["notional_amount"] == 2000.0
        assert d["expiry_date"] == date(2027, 1, 1)
        assert d["unrealized_gain"] == 3.0

    def test_swap_derivative_with_other_ref_instrument(self):
        # descRefInstrmnt carries otherRefInst (not indexBasketInfo), so the
        # underlying name comes from issueTitle.
        swap = {
            "name": "SwapHld2",
            "pctVal": "0.25",
            "valUSD": "25",
            "identifiers": {},
            "derivativeInfo": {
                "swapDeriv": {
                    "@derivCat": "SWP",
                    "counterparties": {
                        "counterpartyName": "CP5",
                        "counterpartyLei": "LEI5",
                    },
                    "descRefInstrmnt": {
                        "otherRefInst": {"issueTitle": "SwapUnder"}
                    },
                    "terminationDt": "2027-06-30",
                    "upfrontPmnt": "10",
                    "pmntCurCd": "USD",
                    "upfrontRcpt": "8",
                    "rcptCurCd": "EUR",
                    "notionalAmt": "2000",
                    "curCd": "USD",
                    "unrealizedAppr": "3",
                }
            },
        }
        d = _transform_nport(_wrap_nport([swap])).result[0].model_dump(
            exclude_none=True
        )
        assert d["derivative_category"] == "SWP"
        assert d["underlying_name"] == "SwapUnder"
        # No indexBasketInfo -> other_id stays unset.
        assert "other_id" not in d

    def test_option_derivative_with_numeric_delta(self):
        # A non-"XXXX" delta is retained and normalized to a fraction.
        opt = {
            "name": "OptHld2",
            "pctVal": "2.0",
            "valUSD": "200",
            "identifiers": {},
            "derivativeInfo": {
                "optionSwaptionWarrantDeriv": {
                    "@derivCat": "OPT",
                    "counterparties": {"counterpartyName": "CP6"},
                    "descRefInstrmnt": {
                        "otherRefInst": {"issueTitle": "UT"}
                    },
                    "putOrCall": "Put",
                    "writtenOrPur": "Written",
                    "expDt": "2025-12-31",
                    "exercisePrice": "10",
                    "exercisePriceCurCd": "USD",
                    "shareNo": "100",
                    "delta": "0.5",
                    "unrealizedAppr": "1",
                }
            },
        }
        d = _transform_nport(_wrap_nport([opt])).result[0].model_dump(
            exclude_none=True
        )
        # delta is retained as-is (not the "XXXX" sentinel that gets skipped).
        assert d["delta"] == "0.5"

    def test_repurchase_agreement(self):
        repo = {
            "name": "RepoHld",
            "pctVal": "0.1",
            "valUSD": "10",
            "identifiers": {},
            "repurchaseAgrmt": {
                "transCat": "Repo",
                "clearedCentCparty": {
                    "@isCleared": "Y",
                    "@centralCounterparty": "CCP",
                },
                "isTriParty": "N",
                "repurchaseRt": "1.5",
                "maturityDt": "2025-01-15",
                "repurchaseCollaterals": {
                    "repurchaseCollateral": {
                        "principalAmt": "1000",
                        "@principalCd": "USD",
                        "collateralVal": "1100",
                        "@collateralCd": "USD",
                        "@invstCat": "Bond",
                    }
                },
            },
        }
        d = _transform_nport(_wrap_nport([repo])).result[0].model_dump(
            exclude_none=True
        )
        assert d["repo_type"] == "Repo"
        assert d["is_cleared"] == "Y"
        assert d["counterparty"] == "CCP"
        assert d["is_tri_party"] == "N"
        assert d["annualized_return"] == pytest.approx(0.015)
        assert d["maturity_date"] == date(2025, 1, 15)
        assert d["principal_amount"] == 1000.0
        assert d["principal_currency"] == "USD"
        assert d["collateral_amount"] == 1100.0
        assert d["collateral_currency"] == "USD"
        assert d["collateral_type"] == "Bond"


class TestNportMetadata:
    """genInfo/fundInfo metadata extraction block."""

    def _fund_info(self):
        return {
            "totAssets": "1000000",
            "totLiabs": "50000",
            "netAssets": "950000",
            "cshNotRptdInCorD": "1234",
            "returnInfo": {
                "monthlyTotReturns": {
                    "monthlyTotReturn": {
                        "@rtn1": "1.0",
                        "@rtn2": "2.0",
                        "@rtn3": "3.0",
                    }
                },
                "othMon1": {"@netRealizedGain": "10", "@netUnrealizedAppr": "20"},
                "othMon2": {"@netRealizedGain": "11", "@netUnrealizedAppr": "21"},
                "othMon3": {"@netRealizedGain": "12", "@netUnrealizedAppr": "22"},
            },
            "mon1Flow": {"@sales": "100", "@redemption": "50"},
            "mon2Flow": {"@sales": "110", "@redemption": "55"},
            "mon3Flow": {"@sales": "120", "@redemption": "60"},
            "borrowers": {
                "borrower": [{"@name": "B1", "@lei": "BLEI", "@aggrVal": "999"}]
            },
        }

    def _gen_info(self):
        return {
            "seriesName": "Test Fund",
            "seriesId": "S123",
            "seriesLei": "LEIFUND",
            "repPdDate": "2025-03-31",
            "repPdEnd": "2025-12-31",
        }

    def test_full_metadata(self):
        holding = {
            "name": "Hld",
            "pctVal": "5.0",
            "valUSD": "1000",
            "identifiers": {},
        }
        res = _transform_nport(
            _wrap_nport(
                [holding], fund_info=self._fund_info(), gen_info=self._gen_info()
            )
        )
        meta = res.metadata
        assert meta["fund_name"] == "Test Fund"
        assert meta["series_id"] == "S123"
        assert meta["lei"] == "LEIFUND"
        assert meta["total_assets"] == 1_000_000.0
        assert meta["total_liabilities"] == 50_000.0
        assert meta["net_assets"] == 950_000.0
        assert meta["cash_and_equivalents"] == "1234"
        # Returns keyed by the three month-end dates, normalized to fractions
        assert meta["returns"] == {
            "2025-01-31": pytest.approx(0.01),
            "2025-02-28": pytest.approx(0.02),
            "2025-03-31": pytest.approx(0.03),
        }
        # Flow + gains structures
        assert meta["flow"]["2025-03-31"] == {
            "creation": 120.0,
            "redemption": 60.0,
        }
        assert meta["gains"]["2025-01-31"] == {
            "realized": 10.0,
            "unrealized": 20.0,
        }
        assert meta["borrowers"] == [
            {"name": "B1", "lei": "BLEI", "value": 999.0}
        ]

    def test_metadata_extraction_error_warns(self):
        # fundInfo present but missing returnInfo -> the metadata block raises
        # internally and is caught with a warning, leaving partial metadata.
        holding = {
            "name": "Hld",
            "pctVal": "5.0",
            "valUSD": "1000",
            "identifiers": {},
        }
        bad_fund_info = {
            "totAssets": "1000000",
            "totLiabs": "50000",
            "netAssets": "950000",
            "cshNotRptdInCorD": "1234",
        }
        with pytest.warns(Warning, match="Error extracting metadata"):
            res = _transform_nport(
                _wrap_nport(
                    [holding],
                    fund_info=bad_fund_info,
                    gen_info=self._gen_info(),
                )
            )
        # genInfo-derived metadata still made it in before the failure.
        assert res.metadata["fund_name"] == "Test Fund"
