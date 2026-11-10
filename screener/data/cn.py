"""A 股：akshare（东方财富）。日线前复权。"""

from __future__ import annotations

import time
from typing import List, Optional

import pandas as pd

from .base import OHLCV_COLUMNS, DataSource, Instrument


class ChinaSource(DataSource):
    market = "cn"
    timeframes = ["1d", "1w", "1M"]

    def __init__(self, cache_root: str = "data/cache"):
        self.cache_root = cache_root

    def universe(self, name: str = "all") -> List[Instrument]:
        from . import universes as u

        if name in u.CSINDEX:
            return u.cached(self.cache_root, f"cn_{name}", lambda: u.csindex(u.CSINDEX[name]))
        if name != "all":
            raise ValueError(f"A 股范围：all / {' / '.join(u.CSINDEX)}")
        return u.cached(self.cache_root, "cn_all", self._all)

    def _all(self) -> List[Instrument]:
        import akshare as ak

        spot = None
        for attempt in range(3):
            try:
                spot = ak.stock_zh_a_spot_em()
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(30 * (attempt + 1))
        out = []
        for _, r in spot.iterrows():
            name_ = str(r["名称"])
            out.append(Instrument(
                symbol=str(r["代码"]), name=name_, market=self.market,
                market_cap=float(r["总市值"]) if pd.notna(r["总市值"]) else None,
                turnover=float(r["成交额"]) if pd.notna(r["成交额"]) else None,
                is_st="ST" in name_.upper(),
            ))
        return out

    def fetch(self, symbol: str, timeframe: str = "1d",
              since: Optional[pd.Timestamp] = None) -> pd.DataFrame:
        import akshare as ak

        start = since.strftime("%Y%m%d") if since is not None else \
            (pd.Timestamp.today() - pd.Timedelta(days=730)).strftime("%Y%m%d")
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start, adjust="qfq")
        if df.empty:
            return pd.DataFrame(columns=OHLCV_COLUMNS)
        df = df.rename(columns={"日期": "date", "开盘": "open", "最高": "high", "最低": "low",
                                "收盘": "close", "成交量": "volume"})
        df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("date")))
        df.index.name = None
        return df[OHLCV_COLUMNS].astype(float)
