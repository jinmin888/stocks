import pandas as pd

from screener.cli import display_time
from screener.config import FilterConfig
from screener.data.base import Instrument
from screener.filters import apply


def inst(**kw):
    return Instrument(symbol=kw.pop("symbol", "X"), market=kw.pop("market", "cn"), **kw)


def test_stock_filters():
    items = [inst(symbol="ok", market_cap=6e9), inst(symbol="st", is_st=True),
             inst(symbol="etf", is_etf=True), inst(symbol="small", market_cap=1e9),
             inst(symbol="nocap")]
    assert [i.symbol for i in apply(items, "cn", FilterConfig())] == ["ok", "nocap"]


def test_crypto_tokenized_filter():
    items = [inst(symbol="BTC/USDT", name="BTC", market="crypto"),
             inst(symbol="MSTRB/USDT", name="MSTRB", market="crypto", is_tokenized=True),
             inst(symbol="XAUM/USDT", name="XAUM", market="crypto")]
    cfg = FilterConfig(extra_tokenized=["XAUM"])
    assert [i.name for i in apply(items, "crypto", cfg)] == ["BTC"]
    assert len(apply(items, "crypto", FilterConfig(exclude_tokenized=False))) == 3


def test_display_time_crypto_close_in_kst():
    start = pd.Timestamp("2026-11-10 04:00", tz="UTC")
    assert display_time(start, "crypto", "4h", "Asia/Seoul") == "2026-11-10 17:00"
    assert display_time(pd.Timestamp("2026-11-10"), "us", "1d", "Asia/Seoul") == "2026-11-10"
