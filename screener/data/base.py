"""统一数据接口：每个市场一个适配器，输出统一格式的 OHLCV。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

import pandas as pd
from pydantic import BaseModel

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


class Instrument(BaseModel):
    symbol: str
    name: str = ""
    market: str
    market_cap: Optional[float] = None  # 当地货币
    turnover: Optional[float] = None  # 最近成交额（当地货币）
    is_etf: bool = False
    is_st: bool = False
    list_date: Optional[pd.Timestamp] = None

    model_config = {"arbitrary_types_allowed": True}


class DataSource(ABC):
    market: str
    timeframes: List[str]

    @abstractmethod
    def universe(self, name: str) -> List[Instrument]:
        """name: 'all'、指数名，或数据源支持的其他范围。"""

    @abstractmethod
    def fetch(self, symbol: str, timeframe: str, since: Optional[pd.Timestamp]) -> pd.DataFrame:
        """返回按时间升序、列为 OHLCV_COLUMNS 的 DataFrame，可包含未收盘 K 线。"""

    def instruments(self, symbols: List[str]) -> List[Instrument]:
        """自定义列表：默认只填代码，子类可补充名称、市值等信息。"""
        return [Instrument(symbol=s, market=self.market) for s in symbols]
