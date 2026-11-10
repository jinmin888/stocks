"""美股 / 港股 / 韩国股市 K 线：yfinance。韩国代码自动补 .KS / .KQ 后缀由调用方处理。"""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from .base import OHLCV_COLUMNS, DataSource, Instrument


class YahooSource(DataSource):
    timeframes = ["1d", "1w", "1M"]

    def __init__(self, market: str, cache_root: str = "data/cache"):
        self.market = market
        self.cache_root = cache_root

    def universe(self, name: str) -> List[Instrument]:
        from . import universes as u

        builders = {("us", "sp500"): u.sp500, ("us", "all"): u.us_all, ("hk", "hsi"): u.hsi}
        build = builders.get((self.market, name))
        if build is None:
            opts = [n for m, n in builders if m == self.market]
            raise ValueError(f"{self.market} 支持的范围：{' / '.join(opts)}")
        items = u.cached(self.cache_root, f"{self.market}_{name}", build)
        if name == "all":
            # 全市场需要逐只查询市值，先剔除 ETF 以减少请求
            items = [i for i in items if not i.is_etf]
            caps = {i.symbol: i.market_cap for i in self.instruments([i.symbol for i in items])}
            for i in items:
                i.market_cap = caps.get(i.symbol)
        return items

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
