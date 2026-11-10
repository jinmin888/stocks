"""对单个标的运行全部已开启的条件，并按组合逻辑输出信号。见 docs/spec.md §5。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional

import pandas as pd

from . import divergence as div_mod
from . import fractal as fr_mod
from .config import ScreenConfig
from .indicators import rsi as rsi_fn

Side = Literal["bottom", "top"]


@dataclass
class Signal:
    side: Side  # bottom = 看涨，top = 看跌
    date: pd.Timestamp
    close: float
    rsi: float
    fractal: Optional[fr_mod.Fractal] = None
    divergences: List[div_mod.Divergence] = field(default_factory=list)

    def to_row(self) -> dict:
        d = self.divergences[0] if self.divergences else None
        return {
            "side": self.side,
            "date": self.date,
            "close": self.close,
            "rsi": round(self.rsi, 2),
            "fractal_strength": self.fractal.strength.name.lower() if self.fractal else None,
            "divergence": d.kind if d else None,
            "divergence_score": round(float(d.score), 2) if d else None,
            "price_change_pct": round(float(d.price_change_pct), 2) if d else None,
            "rsi_diff": round(float(d.rsi_diff), 2) if d else None,
        }


def screen(df: pd.DataFrame, cfg: ScreenConfig) -> List[Signal]:
    """df: 按时间升序，列 open/high/low/close/volume，只含已收盘 K 线。"""
    if len(df) < 3:
        return []
    fractals = fr_mod.detect(df, cfg.fractal)
    rsi = rsi_fn(df["close"], cfg.divergence.rsi_period)
    n = len(df)

    fr_sig = fr_mod.latest_signal(fractals, n, cfg.fractal) if cfg.fractal.enabled else None
    divs = div_mod.detect(fractals, rsi, cfg.divergence) if cfg.divergence.enabled else []

    sides: List[Side] = ["bottom", "top"] if cfg.direction == "both" else [cfg.direction]
    out: List[Signal] = []
    for side in sides:
        f_hit = fr_sig if fr_sig is not None and fr_sig.type == side else None
        d_hit = [d for d in divs if d.side == side]
        checks = []
        if cfg.fractal.enabled:
            checks.append(f_hit is not None)
        if cfg.divergence.enabled:
            checks.append(bool(d_hit))
        if not checks:
            continue
        ok = all(checks) if cfg.logic == "and" else any(checks)
        if not ok:
            continue
        out.append(Signal(
            side=side,
            date=df.index[-1],
            close=float(df["close"].iloc[-1]),
            rsi=float(rsi.iloc[-1]),
            fractal=f_hit,
            divergences=sorted(d_hit, key=lambda d: d.score, reverse=True),
        ))
    return out
