"""Screener configuration. Every option in docs/spec.md maps to a field here."""

from __future__ import annotations

from enum import IntEnum
from typing import Literal, Optional

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


class ScreenConfig(BaseModel):
    fractal: FractalConfig = FractalConfig()
    divergence: DivergenceConfig = DivergenceConfig()
    logic: Literal["and", "or"] = "and"
    direction: Literal["bottom", "top", "both"] = "both"
