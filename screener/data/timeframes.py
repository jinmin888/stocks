from __future__ import annotations

import pandas as pd

from .base import OHLCV_COLUMNS

DURATION = {
    "15m": pd.Timedelta(minutes=15),
    "1h": pd.Timedelta(hours=1),
    "4h": pd.Timedelta(hours=4),
    "1d": pd.Timedelta(days=1),
    "1w": pd.Timedelta(weeks=1),
}


def resample(daily: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """由日线合成周线（周一为起点）或月线。索引为每根 K 线的起始日期。"""
    if timeframe == "1d":
        return daily
    rule = {"1w": "W-MON", "1M": "MS"}[timeframe]
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    kw = {"label": "left", "closed": "left"} if timeframe == "1w" else {}
    out = daily[OHLCV_COLUMNS].resample(rule, **kw).agg(agg)
    return out.dropna(subset=["open"])


def bar_end(start: pd.Timestamp, timeframe: str) -> pd.Timestamp:
    if timeframe == "1M":
        return start + pd.offsets.MonthBegin(1)
    return start + DURATION[timeframe]


def drop_unclosed(df: pd.DataFrame, timeframe: str, now: pd.Timestamp) -> pd.DataFrame:
    """丢弃尚未收盘的最后一根 K 线。now 与索引须同一时区。"""
    if df.empty:
        return df
    if bar_end(df.index[-1], timeframe) > now:
        return df.iloc[:-1]
    return df
