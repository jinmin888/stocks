"""Screener configuration. Every option in docs/spec.md maps to a field here."""

from __future__ import annotations

from enum import IntEnum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class Strength(IntEnum):
    WEAK = 1
    MEDIUM = 2
    STRONG = 3


class FractalConfig(BaseModel):
    enabled: bool = True
    inclusion: bool = True  # 包含关系处理
    strict_bi: bool = True  # 严格笔规则过滤
    recent_bars: int = Field(1, ge=1)  # K3（或开启确认时的 K4）须在最近 N 根已收盘 K 线内
    min_strength: Optional[Strength] = None  # None = 不过滤，只标注
    confirm_k4: bool = False
    volume_check: bool = False
    volume_ma: int = Field(5, ge=1)


class DivergenceConfig(BaseModel):
    enabled: bool = True
    rsi_period: int = Field(14, ge=2)
    regular: bool = True
    hidden: bool = False
    min_gap: int = Field(5, ge=1)
    max_gap: int = Field(60, ge=1)
    # None 表示关闭该过滤；只作用于常规背离的第一个点
    oversold: Optional[float] = 30.0
    overbought: Optional[float] = 70.0
    recent_bars: int = Field(3, ge=1)
    min_fractal_strength: Optional[Strength] = None  # 第二个分型的最低强度
    # 两个分型点价格至少相差 X%（常规与隐藏背离都适用）；None 表示关闭
    min_price_change_pct: Optional[float] = 0.5
    # 两个分型点 RSI 至少相差多少；None 表示关闭
    min_rsi_diff: Optional[float] = 3.0
    # 强度分 = RSI 差值 × rsi_weight + 价格差% × price_weight（以 RSI 为主，权重待回测调整）
    score_rsi_weight: float = 1.0
    score_price_weight: float = 0.2


class FilterConfig(BaseModel):
    exclude_st: bool = True
    exclude_etf: bool = True
    min_list_days: Optional[int] = 60
    # 市值下限（当地货币）；None 表示不过滤
    min_market_cap: Dict[str, Optional[float]] = {
        "cn": 5e9, "hk": 5e9, "us": 1e9, "kr": 1e11, "crypto": None,
    }
    min_turnover: Dict[str, Optional[float]] = {}
    # 加密货币：剔除代币化股票（如 MSTRB、QQQB）和黄金等实物资产代币
    exclude_tokenized: bool = True
    extra_tokenized: List[str] = []  # 手动补充的剔除名单（币种代码，如 "XAUM"）


class ScreenConfig(BaseModel):
    fractal: FractalConfig = FractalConfig()
    divergence: DivergenceConfig = DivergenceConfig()
    logic: Literal["and", "or"] = "and"
    direction: Literal["bottom", "top", "both"] = "both"
    filters: FilterConfig = FilterConfig()
    display_tz: str = "Asia/Seoul"  # 加密货币信号时间的显示时区
