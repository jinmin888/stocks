"""A 股日线（前复权）：优先东方财富（akshare），被限流时自动改用腾讯行情。"""

from __future__ import annotations

import logging
import threading
import time
from typing import List, Optional

import pandas as pd
import requests

from .base import OHLCV_COLUMNS, DataSource, Instrument

log = logging.getLogger("screener.cn")

TENCENT_URL = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
EM_COOLDOWN = 600  # 东方财富失败后暂停使用的秒数（反复请求会延长限流）
_em_blocked_until = 0.0
_em_lock = threading.Lock()


def _tencent_code(symbol: str) -> str:
    if symbol.startswith(("4", "8", "92")):  # 北交所（先判断 92，避免被当成沪市 9 开头）
        return "bj" + symbol
    if symbol.startswith(("6", "9")):
        return "sh" + symbol
    return "sz" + symbol


def fetch_tencent(symbol: str, since: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    """腾讯行情：返回截至今天最近最多 640 根日线（约 2.5 年），成交量单位为手（与东方财富一致）。"""
    code = _tencent_code(symbol)
    today = pd.Timestamp.today()
    start = (since or today - pd.Timedelta(days=730)).strftime("%Y-%m-%d")
    r = requests.get(TENCENT_URL, params={"param": f"{code},day,{start},{today:%Y-%m-%d},640,qfq"},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()
    data = (r.json().get("data") or {}).get(code) or {}
    rows = data.get("qfqday") or data.get("day") or []
    if not rows:
        return pd.DataFrame(columns=OHLCV_COLUMNS)
    df = pd.DataFrame([x[:6] for x in rows], columns=["date", "open", "close", "high", "low", "volume"])
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("date")))
    df.index.name = None
    df = df[OHLCV_COLUMNS].astype(float)
    if code.startswith(("sh688", "sh689")):  # 腾讯只有科创板返回「股」，换算成「手」
        df["volume"] = df["volume"] / 100
    return df[df.index >= pd.Timestamp(start)]


def _fetch_eastmoney(symbol: str, since: Optional[pd.Timestamp]) -> pd.DataFrame:
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
        global _em_blocked_until
        if time.time() >= _em_blocked_until:
            try:
                return _fetch_eastmoney(symbol, since)
            except Exception as e:
                with _em_lock:
                    _em_blocked_until = time.time() + EM_COOLDOWN
                log.warning("东方财富取数失败（%s），%d 秒内改用腾讯行情", type(e).__name__, EM_COOLDOWN)
        return fetch_tencent(symbol, since)
