"""美股 / 港股 / 韩国股市 K 线：yfinance。韩国代码自动补 .KS / .KQ 后缀由调用方处理。"""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from .base import OHLCV_COLUMNS, DataSource, Instrument


class YahooSource(DataSource):
    timeframes = ["1d", "1w", "1M"]

    def __init__(self, market: str):
        self.market = market

    def universe(self, name: str) -> List[Instrument]:
        raise NotImplementedError(f"{self.market}: 指数成分股 / 全市场列表尚未接入，请先使用自定义列表")

    def instruments(self, symbols: List[str]) -> List[Instrument]:
        import yfinance as yf

        out = []
        for s in symbols:
            cap = None
            try:
                cap = float(yf.Ticker(s).fast_info["marketCap"])
            except Exception:
                pass
            out.append(Instrument(symbol=s, market=self.market, market_cap=cap))
        return out

    def fetch(self, symbol: str, timeframe: str = "1d",
              since: Optional[pd.Timestamp] = None) -> pd.DataFrame:
        import yfinance as yf

        kw = {"start": since.strftime("%Y-%m-%d")} if since is not None else {"period": "2y"}
        df = yf.Ticker(symbol).history(interval="1d", auto_adjust=True, **kw)
        if df.empty:
            return pd.DataFrame(columns=OHLCV_COLUMNS)
        df = df.rename(columns=str.lower)[OHLCV_COLUMNS]
        df.index = pd.DatetimeIndex(df.index.tz_localize(None).normalize())
        return df.astype(float)
