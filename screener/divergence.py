"""RSI 背离，以顶底分型作为高低点。见 docs/spec.md §1。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional

import numpy as np
import pandas as pd

from .config import DivergenceConfig
from .fractal import Fractal

DivKind = Literal["regular", "hidden"]


@dataclass
class Divergence:
    side: Literal["top", "bottom"]
    kind: DivKind
    first: Fractal
    second: Fractal
    p1: float
    p2: float
    r1: float
    r2: float
    gap: int
    price_change_pct: float
    rsi_diff: float
    score: float  # 综合强度分（仅排序用，以 RSI 差值为主，权重待回测调整）


def _fractal_rsi(f: Fractal, rsi: np.ndarray) -> float:
    window = rsi[f.start:f.end + 1]
    if np.all(np.isnan(window)):
        return float("nan")
    return float(np.nanmin(window) if f.type == "bottom" else np.nanmax(window))


def detect(fractals: List[Fractal], rsi: pd.Series, cfg: DivergenceConfig) -> List[Divergence]:
    """检查最新的顶分型、底分型各自与前一个同类分型之间是否构成背离。"""
    r = rsi.to_numpy(float)
    n = len(r)
    out: List[Divergence] = []
    for side in ("bottom", "top"):
        same = [f for f in fractals if f.type == side]
        if len(same) < 2:
            continue
        f1, f2 = same[-2], same[-1]
        if f2.end < n - cfg.recent_bars:
            continue
        if cfg.min_fractal_strength is not None and f2.strength < cfg.min_fractal_strength:
            continue
        gap = f2.extreme_pos - f1.extreme_pos
        if not (cfg.min_gap <= gap <= cfg.max_gap):
            continue
        r1, r2 = _fractal_rsi(f1, r), _fractal_rsi(f2, r)
        if np.isnan(r1) or np.isnan(r2):
            continue
        p1, p2 = f1.price, f2.price

        kind: Optional[DivKind] = None
        if side == "bottom":
            if p2 < p1 and r2 > r1 and cfg.regular:
                if cfg.oversold is None or r1 < cfg.oversold:
                    kind = "regular"
            elif p2 > p1 and r2 < r1 and cfg.hidden:
                kind = "hidden"
        else:
            if p2 > p1 and r2 < r1 and cfg.regular:
                if cfg.overbought is None or r1 > cfg.overbought:
                    kind = "regular"
            elif p2 < p1 and r2 > r1 and cfg.hidden:
                kind = "hidden"
        if kind is None:
            continue

        price_pct = abs(p2 - p1) / p1 * 100 if p1 else 0.0
        if cfg.min_price_change_pct is not None and price_pct < cfg.min_price_change_pct:
            continue
        rsi_diff = abs(r2 - r1)
        if cfg.min_rsi_diff is not None and rsi_diff < cfg.min_rsi_diff:
            continue
        score = rsi_diff * cfg.score_rsi_weight + price_pct * cfg.score_price_weight
        out.append(Divergence(side, kind, f1, f2, p1, p2, r1, r2, gap,
                              price_pct, rsi_diff, score=score))
    return out
