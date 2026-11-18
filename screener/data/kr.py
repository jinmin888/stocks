"""韩国股市：列表、名称、市值、成交额来自 KRX（pykrx，需要 KRX_ID / KRX_PW 环境变量登录）；
K 线来自 yfinance（KOSPI 后缀 .KS，KOSDAQ 后缀 .KQ）。"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

import pandas as pd

from .base import DataSource, Instrument
from .yahoo import YahooSource

SUFFIX = {"KOSPI": ".KS", "KOSDAQ": ".KQ"}
INDEX_CODES = {"kospi200": "1028", "kosdaq150": "2203"}


log = logging.getLogger("screener.kr")


def _name_map(date: str, market: str) -> Dict[str, str]:
    """一次取整个市场的「代码 → 名称」。失败或返回值不是字符串时给空表（名称只是显示用，不影响扫描）。
    （pykrx 的 get_market_ticker_name 失败时会返回空 DataFrame 而不是报错，所以不逐只调用它。）"""
    from pykrx.website import krx

    try:
        s = krx.get_market_ticker_and_name(date, market)
    except Exception as e:
        log.warning("KRX %s 종목명 조회 실패（%s），名称留空", market, type(e).__name__)
        return {}
    if not isinstance(s, pd.Series):
        return {}
    return {str(k): v.strip() for k, v in s.items() if isinstance(v, str)}


def _require_login() -> None:
    if not (os.environ.get("KRX_ID") and os.environ.get("KRX_PW")):
        raise RuntimeError("韩国股市列表需要 KRX 账号：请设置环境变量 KRX_ID 和 KRX_PW")


def _num(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


class KoreaSource(YahooSource):
    def __init__(self, cache_root: str = "data/cache"):
        super().__init__("kr", cache_root)
        self._suffix: Dict[str, str] = {}

    def _listing(self) -> pd.DataFrame:
        from pykrx import stock

        _require_login()
        date = stock.get_nearest_business_day_in_a_week()
        frames = []
        for mkt, suf in SUFFIX.items():
            cap = stock.get_market_cap(date, market=mkt)
            if cap.empty:
                raise RuntimeError(f"KRX 未返回 {mkt} 数据，请检查账号是否可以登录 data.krx.co.kr")
            names = _name_map(date, mkt)
            cap = cap.assign(suffix=suf, name=[names.get(str(t), "") for t in cap.index])
            frames.append(cap)
        df = pd.concat(frames)
        self._suffix = df["suffix"].to_dict()
        return df

    def universe(self, name: str = "all") -> List[Instrument]:
        from pykrx import stock

        df = self._listing()
        name = name.lower()
        if name in INDEX_CODES:
            members = stock.get_index_portfolio_deposit_file(INDEX_CODES[name])
            # 실패 시 pykrx 는 빈 DataFrame 을 돌려준다
            if not isinstance(members, (list, tuple)) or not members:
                raise RuntimeError(f"KRX 지수 구성 종목（{name}）을 가져오지 못했습니다. KRX 계정 로그인 상태를 확인하세요")
            df = df[df.index.isin(set(map(str, members)))]
        elif name in ("kospi", "kosdaq"):
            df = df[df["suffix"] == SUFFIX[name.upper()]]
        elif name != "all":
            raise ValueError(f"韩国股市范围：all / kospi / kosdaq / {' / '.join(INDEX_CODES)}")
        out = []
        for t, r in df.iterrows():
            name = r["name"] if isinstance(r["name"], str) else ""
            out.append(Instrument(
                symbol=str(t) + r["suffix"], name=name, market=self.market,
                market_cap=_num(r.get("시가총액")), turnover=_num(r.get("거래대금")),
                # 스팩（SPAC）没有实际业务，按与 ETF 相同的开关剔除
                is_etf="스팩" in name,
            ))
        return out

    def instruments(self, symbols: List[str]) -> List[Instrument]:
        return super().instruments([self._resolve(s) for s in symbols])

    def _resolve(self, symbol: str) -> str:
        """'005930' → '005930.KS'；已带后缀的原样返回。"""
        if "." in symbol:
            return symbol
        if symbol in self._suffix:
            return symbol + self._suffix[symbol]
        if os.environ.get("KRX_ID"):
            try:
                self._listing()
                if symbol in self._suffix:
                    return symbol + self._suffix[symbol]
            except Exception:
                pass
        # 没有 KRX 账号时：先试 KOSPI，取不到再试 KOSDAQ
        return symbol + (".KS" if not super().fetch(symbol + ".KS").empty else ".KQ")

    def fetch(self, symbol: str, timeframe: str = "1d",
              since: Optional[pd.Timestamp] = None) -> pd.DataFrame:
        return super().fetch(self._resolve(symbol), timeframe, since)
