"""Shared deterministic real-data fixtures for the charting test suite."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from openbb_core.provider.abstract.data import Data

SYMBOLS = ("AAA", "BBB", "CCC", "DDD")


def _make_ohlcv(
    seed: int, periods: int = 200, start: str = "2023-01-01"
) -> pd.DataFrame:
    """Build a deterministic, valid OHLCV frame with a ``date`` index."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=periods, freq="D")
    close = 100 + np.cumsum(rng.normal(0, 1, periods))
    open_ = close + rng.normal(0, 0.5, periods)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.5, periods))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.5, periods))
    volume = rng.integers(1_000_000, 5_000_000, periods)
    frame = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )
    frame.index.name = "date"
    return frame


@pytest.fixture
def ohlcv_df() -> pd.DataFrame:
    """A single-symbol OHLCV DataFrame indexed by date (200 rows)."""
    return _make_ohlcv(seed=42)


@pytest.fixture
def ohlcv_records(ohlcv_df) -> list[dict]:
    """The OHLCV frame as a list of ``date``-stamped record dicts."""
    out = ohlcv_df.reset_index()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out.to_dict(orient="records")


@pytest.fixture
def ohlcv_data(ohlcv_records) -> list[Data]:
    """The OHLCV records as real ``Data`` models."""
    return [Data.model_validate(row) for row in ohlcv_records]


@pytest.fixture
def multi_close_df() -> pd.DataFrame:
    """A multi-symbol close-price frame (wide), indexed by date."""
    frames = {sym: _make_ohlcv(seed=i)["close"] for i, sym in enumerate(SYMBOLS)}
    wide = pd.DataFrame(frames)
    wide.index.name = "date"
    return wide
