from __future__ import annotations

from .base import DataSource


def get_source(market: str, **kw) -> DataSource:
    if market == "crypto":
        from .crypto import CryptoSource
        return CryptoSource(**kw)
    if market == "cn":
        from .cn import ChinaSource
        return ChinaSource()
    if market in ("us", "hk", "kr"):
        from .yahoo import YahooSource
        return YahooSource(market)
    raise ValueError(f"unknown market: {market}")
