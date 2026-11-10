"""加密货币：ccxt。默认 Binance，走官方公开行情域名 data-api.binance.vision（不受地区限制）。"""

from __future__ import annotations

import os
from typing import List, Optional

import pandas as pd

from .base import OHLCV_COLUMNS, DataSource, Instrument

STABLECOINS = {
    "USDT", "USDC", "FDUSD", "TUSD", "DAI", "BUSD", "USDP", "PYUSD", "USDE", "USD1", "U",
    "EUR", "EURI", "AEUR", "XUSD", "USDS", "RLUSD", "BFUSD", "UST", "GUSD", "LUSD",
}


class CryptoSource(DataSource):
    market = "crypto"
    timeframes = ["15m", "1h", "4h", "1d", "1w", "1M"]

    def __init__(self, exchange: str = "binance", quote: str = "USDT"):
        import ccxt

        opts: dict = {"enableRateLimit": True}
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if proxy:
            opts["httpsProxy"] = proxy  # ccxt 不读取环境变量代理
        if exchange == "binance":
            opts["options"] = {"defaultType": "spot", "fetchMarkets": {"types": ["spot"]}}
        self.ex = getattr(ccxt, exchange)(opts)
        if exchange == "binance":
            self.ex.urls["api"]["public"] = "https://data-api.binance.vision/api/v3"
        self.quote = quote

    def universe(self, name: str = "top100") -> List[Instrument]:
        """'topN'：按 24h 成交额取前 N，剔除稳定币；'all'：全部现货交易对。"""
        self.ex.load_markets()
        tickers = self.ex.fetch_tickers()
        rows = []
        for sym, m in self.ex.markets.items():
            if not (m.get("spot") and m.get("active", True) and m.get("quote") == self.quote):
                continue
            if m.get("base") in STABLECOINS:
                continue
            t = tickers.get(sym) or {}
            rows.append(Instrument(symbol=sym, name=m.get("base", ""), market=self.market,
                                   turnover=t.get("quoteVolume") or 0.0))
        rows.sort(key=lambda i: i.turnover or 0, reverse=True)
        if name.startswith("top"):
            rows = rows[: int(name[3:] or 100)]
        return rows

    def fetch(self, symbol: str, timeframe: str, since: Optional[pd.Timestamp] = None,
              limit: int = 500) -> pd.DataFrame:
        """since=None 时取最近 limit 根；否则从 since 起分页取到最新。"""
        tf_ms = self.ex.parse_timeframe(timeframe) * 1000
        if since is None:
            start = self.ex.milliseconds() - tf_ms * limit
        else:
            start = int(pd.Timestamp(since).tz_convert("UTC").timestamp() * 1000)
        data: list = []
        while True:
            batch = self.ex.fetch_ohlcv(symbol, timeframe, since=start, limit=1000)
            if not batch:
                break
            data += batch
            nxt = batch[-1][0] + tf_ms
            if nxt <= start or len(batch) < 2:
                break
            start = nxt
            if start > self.ex.milliseconds():
                break
        df = pd.DataFrame(data, columns=["ts"] + OHLCV_COLUMNS).drop_duplicates("ts")
        df.index = pd.to_datetime(df.pop("ts"), unit="ms", utc=True)
        df.index.name = None
        return df.astype(float)
