from __future__ import annotations

from .base import DataSource


DEFAULT_UNIVERSE = {"crypto": "top100", "cn": "all", "kr": "all", "us": "sp500", "hk": "hsi"}


def get_source(market: str, cache_root: str = "data/cache", **kw) -> DataSource:
    if market == "crypto":
        from .crypto import CryptoSource
        return CryptoSource(**kw)
    if market == "cn":
        from .cn import ChinaSource
        return ChinaSource(cache_root)
    if market == "kr":
        from .kr import KoreaSource
        return KoreaSource(cache_root)
    if market in ("us", "hk"):
        from .yahoo import YahooSource
        return YahooSource(market, cache_root)
    raise ValueError(f"unknown market: {market}")
