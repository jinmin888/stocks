"""指数成分股 / 全市场代码表。结果按天缓存，避免重复请求。"""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from typing import Callable, List

import pandas as pd
import requests

from .base import Instrument

log = logging.getLogger("screener.universes")
HEADERS = {"User-Agent": "Mozilla/5.0 (stock-screener)"}
CSINDEX = {"csi300": "000300", "csi500": "000905", "csi1000": "000852", "sse50": "000016"}
EXCLUDE_WORDS = ("Warrant", "Unit", "Right", "Preferred", "Depositary Share", "Notes")


def _load(path: Path) -> List[Instrument]:
    return [Instrument.model_validate(x) for x in json.loads(path.read_text())]


def cached(root: str | Path, key: str, build: Callable[[], List[Instrument]]) -> List[Instrument]:
    """当天的列表直接用缓存；否则重新获取。获取失败时退回最近一次成功的列表（会记录警告）。"""
    folder = Path(root) / "universe"
    path = folder / f"{key}_{pd.Timestamp.today():%Y%m%d}.json"
    if path.exists():
        return _load(path)
    try:
        items = build()
        if not items:
            raise RuntimeError("列表为空")
    except Exception as e:
        older = sorted(folder.glob(f"{key}_????????.json")) if folder.exists() else []
        if not older:
            raise
        log.warning("%s 列表获取失败（%s: %s），使用 %s 的旧列表", key, type(e).__name__, str(e)[:120], older[-1].name)
        return _load(older[-1])
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([i.model_dump(mode="json") for i in items], ensure_ascii=False))
    for old in folder.glob(f"{key}_????????.json"):  # 只保留最新一份
        if old != path:
            old.unlink(missing_ok=True)
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


CSINDEX_SIZE = {"000300": 300, "000905": 500, "000852": 1000, "000016": 50}


def _sina_index_members(code: str) -> List[tuple]:
    """新浪新版指数成分接口（按代码排序，无分页重复）。只支持沪深300、中证500、上证50 等部分指数。"""
    import akshare as ak

    df = ak.index_stock_cons_sina(symbol=code)
    if df.empty:
        return []
    return list(zip(df["code"], df["name"]))


def csindex(code: str) -> List[Instrument]:
    """中证指数成分股。
    1. 中证指数公司官方文件（oss-ch.csindex.com.cn）——部分网络无法解析该域名
    2. 新浪财经新版接口（vip.stock.finance.sina.com.cn），成分数量与指数规模一致才采用
    都失败时抛出异常，由 cached() 退回上一次成功的列表。
    （新浪旧版分页接口会重复、漏掉约 1/4 成分股，不使用。）"""
    import akshare as ak

    errors = []
    try:
        df = ak.index_stock_cons_csindex(symbol=code)
        pairs = list(zip(df["成分券代码"], df["成分券名称"]))
    except Exception as e:
        errors.append(f"中证指数官网: {type(e).__name__}")
        log.warning("中证指数官网获取 %s 成分股失败（%s），改用新浪财经", code, type(e).__name__)
        try:
            pairs = _sina_index_members(code)
        except Exception as e2:
            errors.append(f"新浪财经: {type(e2).__name__}")
            pairs = []
        expected = CSINDEX_SIZE.get(code)
        unique = {str(c).zfill(6) for c, _ in pairs}
        if not pairs or (expected and abs(len(unique) - expected) > expected * 0.02):
            if pairs:
                errors.append(f"新浪财经: 成分数量 {len(unique)} 与指数规模 {expected} 不符")
            raise RuntimeError(f"无法获取指数 {code} 的成分股（{'；'.join(errors) or '新浪财经无此指数'}）")
    items = [Instrument(symbol=str(c).zfill(6), name=str(n), market="cn", is_st="ST" in str(n).upper())
             for c, n in pairs]
    return list({i.symbol: i for i in items}.values())  # 去重
