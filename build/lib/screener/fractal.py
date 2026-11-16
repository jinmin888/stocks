"""K 线包含处理、顶底分型识别、强弱分级与严格笔过滤。见 docs/spec.md §2。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional

import numpy as np
import pandas as pd

from .config import FractalConfig, Strength

FractalType = Literal["top", "bottom"]


@dataclass
class MergedBar:
    high: float
    low: float
    open: float  # 组内第一根原始 K 线开盘价
    close: float  # 组内最后一根原始 K 线收盘价
    volume: float  # 组内成交量之和
    start: int  # 原始 K 线位置（含）
    end: int  # 原始 K 线位置（含）
    extreme_high: int  # 组内最高价所在原始 K 线位置
    extreme_low: int  # 组内最低价所在原始 K 线位置


@dataclass
class Fractal:
    type: FractalType
    k2: int  # 合并 K 线序列中 K2 的位置
    price: float  # 顶：K2 最高价；底：K2 最低价
    extreme_pos: int  # 极值所在原始 K 线位置
    start: int  # K1 起始原始位置
    end: int  # K3 结束原始位置（分型确认的 K 线）
    strength: Strength
    k4_ok: Optional[bool] = None  # K4 是否未破 K2 极值；None = 尚无 K4
    k4_end: Optional[int] = None  # K4 结束原始位置


def merge_bars(df: pd.DataFrame, inclusion: bool = True) -> List[MergedBar]:
    """包含关系处理。上升取高高，下降取低低；方向由前两根合并 K 线比较决定。"""
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    o = df["open"].to_numpy(float)
    c = df["close"].to_numpy(float)
    v = df["volume"].to_numpy(float) if "volume" in df else np.zeros(len(df))

    bars: List[MergedBar] = []
    for i in range(len(df)):
        nb = MergedBar(h[i], l[i], o[i], c[i], v[i], i, i, i, i)
        if inclusion and bars:
            last = bars[-1]
            contains = (last.high >= nb.high and last.low <= nb.low) or (
                nb.high >= last.high and nb.low <= last.low
            )
            if contains:
                up = True if len(bars) < 2 else last.high > bars[-2].high
                pick = max if up else min
                new_high = pick(last.high, nb.high)
                new_low = pick(last.low, nb.low)
                last.extreme_high = last.extreme_high if new_high == last.high else i
                last.extreme_low = last.extreme_low if new_low == last.low else i
                last.high, last.low = new_high, new_low
                last.close = nb.close
                last.volume += nb.volume
                last.end = i
                continue
        bars.append(nb)
    return bars


def _strength(k1: MergedBar, k2: MergedBar, k3: MergedBar, kind: FractalType,
              bars: List[MergedBar], idx3: int, cfg: FractalConfig) -> Strength:
    mid = (k1.open + k1.close) / 2
    if kind == "bottom":
        through = k3.close > k1.high
        candle_ok = k3.close > k3.open
        past_mid = k3.close > mid
    else:
        through = k3.close < k1.low
        candle_ok = k3.close < k3.open
        past_mid = k3.close < mid

    if through:
        s = Strength.STRONG if candle_ok else Strength.MEDIUM
    elif past_mid:
        s = Strength.MEDIUM
    else:
        s = Strength.WEAK

    if s == Strength.STRONG and cfg.volume_check:
        prev = bars[max(0, idx3 - cfg.volume_ma):idx3]
        ma = sum(b.volume for b in prev) / len(prev) if prev else 0.0
        if not (k3.volume > k2.volume and k3.volume > ma):
            s = Strength.MEDIUM
    return s


def find_fractals(bars: List[MergedBar], cfg: FractalConfig) -> List[Fractal]:
    """在合并后的 K 线上识别全部原始分型（未过滤）。"""
    out: List[Fractal] = []
    for i in range(1, len(bars) - 1):
        k1, k2, k3 = bars[i - 1], bars[i], bars[i + 1]
        kind: Optional[FractalType] = None
        if k2.high > k1.high and k2.high > k3.high and k2.low > k1.low and k2.low > k3.low:
            kind = "top"
        elif k2.low < k1.low and k2.low < k3.low and k2.high < k1.high and k2.high < k3.high:
            kind = "bottom"
        if kind is None:
            continue
        f = Fractal(
            type=kind,
            k2=i,
            price=k2.high if kind == "top" else k2.low,
            extreme_pos=k2.extreme_high if kind == "top" else k2.extreme_low,
            start=k1.start,
            end=k3.end,
            strength=_strength(k1, k2, k3, kind, bars, i + 1, cfg),
        )
        if i + 2 < len(bars):
            k4 = bars[i + 2]
            f.k4_ok = k4.low >= k2.low if kind == "bottom" else k4.high <= k2.high
            f.k4_end = k4.end
        out.append(f)
    return out


def filter_bi(fractals: List[Fractal]) -> List[Fractal]:
    """严格笔规则：顶底交替；相邻顶底不共用 K 线且中间至少 1 根独立 K 线；
    连续同类分型保留更极端者。"""
    kept: List[Fractal] = []
    for f in fractals:
        if not kept:
            kept.append(f)
            continue
        last = kept[-1]
        if f.type == last.type:
            more_extreme = f.price > last.price if f.type == "top" else f.price < last.price
            if more_extreme:
                kept[-1] = f
            continue
        if f.k2 - last.k2 < 4:
            continue
        top, bottom = (f, last) if f.type == "top" else (last, f)
        if top.price <= bottom.price:
            continue
        kept.append(f)
    return kept


def alternate_only(fractals: List[Fractal]) -> List[Fractal]:
    """非严格模式：仅要求顶底交替，同类取更极端者。"""
    kept: List[Fractal] = []
    for f in fractals:
        if kept and kept[-1].type == f.type:
            more_extreme = f.price > kept[-1].price if f.type == "top" else f.price < kept[-1].price
            if more_extreme:
                kept[-1] = f
            continue
        kept.append(f)
    return kept


def detect(df: pd.DataFrame, cfg: FractalConfig) -> List[Fractal]:
    """完整流程：包含处理 → 分型识别 → 过滤。返回按时间排序的有效分型。"""
    bars = merge_bars(df, cfg.inclusion)
    raw = find_fractals(bars, cfg)
    return filter_bi(raw) if cfg.strict_bi else alternate_only(raw)


def latest_signal(fractals: List[Fractal], n_bars: int, cfg: FractalConfig) -> Optional[Fractal]:
    """筛选条件：最新的有效分型是否在时效内、满足确认与强度要求。"""
    if not fractals:
        return None
    f = fractals[-1]
    if cfg.confirm_k4:
        if not f.k4_ok or f.k4_end is None:
            return None
        anchor = f.k4_end
    else:
        anchor = f.end
    if anchor < n_bars - cfg.recent_bars:
        return None
    if cfg.min_strength is not None and f.strength < cfg.min_strength:
        return None
    return f
