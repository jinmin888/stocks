"""指数成分股 / 全市场代码表。结果按天缓存，避免重复请求。"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Callable, List

import pandas as pd
import requests

from .base import Instrument

HEADERS = {"User-Agent": "Mozilla/5.0 (stock-screener)"}
CSINDEX = {"csi300": "000300", "csi500": "000905", "csi1000": "000852", "sse50": "000016"}
EXCLUDE_WORDS = ("Warrant", "Unit", "Right", "Preferred", "Depositary Share", "Notes")


def cached(root: str | Path, key: str, build: Callable[[], List[Instrument]]) -> List[Instrument]:
    path = Path(root) / "universe" / f"{key}_{pd.Timestamp.today():%Y%m%d}.json"
    if path.exists():
        return [Instrument.model_validate(x) for x in json.loads(path.read_text())]
    items = build()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([i.model_dump(mode="json") for i in items], ensure_ascii=False))
    return items


def _wiki_tables(page: str) -> List[pd.DataFrame]:
    r = requests.get(f"https://en.wikipedia.org/wiki/{page}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return pd.read_html(io.StringIO(r.text))


def sp500() -> List[Instrument]:
    t = _wiki_tables("List_of_S%26P_500_companies")[0]
    return [Instrument(symbol=str(s).replace(".", "-"), name=str(n), market="us")
            for s, n in zip(t["Symbol"], t["Security"])]


def us_all() -> List[Instrument]:
    """纳斯达克官方代码表（NASDAQ + NYSE 等），带 ETF 标记。不含市值。"""
    out: List[Instrument] = []
    for f, sym_col in (("nasdaqlisted.txt", "Symbol"), ("otherlisted.txt", "ACT Symbol")):
        r = requests.get(f"https://www.nasdaqtrader.com/dynamic/SymDir/{f}", timeout=30)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text), sep="|", dtype=str).dropna(subset=[sym_col])
        df = df[~df[sym_col].str.startswith("File Creation Time")]
        df = df[df["Test Issue"] == "N"]
        for sym, name, etf in zip(df[sym_col], df["Security Name"], df["ETF"]):
            if "$" in sym or any(w in str(name) for w in EXCLUDE_WORDS):
                continue
            out.append(Instrument(symbol=sym.replace(".", "-"), name=str(name), market="us",
                                  is_etf=etf == "Y"))
    return out


def hsi() -> List[Instrument]:
    for t in _wiki_tables("Hang_Seng_Index"):
        if "Ticker" in t.columns and len(t) > 50:
            return [Instrument(symbol=f"{int(str(s).split(':')[-1]):04d}.HK", name=str(n), market="hk")
                    for s, n in zip(t["Ticker"], t["Name"])]
    raise RuntimeError("维基百科恒生指数成分股表格式已变化")


def csindex(code: str) -> List[Instrument]:
    import akshare as ak

    df = ak.index_stock_cons_csindex(symbol=code)
    return [Instrument(symbol=str(s).zfill(6), name=str(n), market="cn",
                       is_st="ST" in str(n).upper())
            for s, n in zip(df["成分券代码"], df["成分券名称"])]
