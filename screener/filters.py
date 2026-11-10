from __future__ import annotations

from typing import List

import pandas as pd

from .config import FilterConfig
from .data.base import Instrument


def apply(instruments: List[Instrument], market: str, cfg: FilterConfig,
          today: pd.Timestamp | None = None) -> List[Instrument]:
    today = today or pd.Timestamp.today().normalize()
    cap = cfg.min_market_cap.get(market)
    turnover = cfg.min_turnover.get(market)
    out = []
    for i in instruments:
        if cfg.exclude_st and i.is_st:
            continue
        if cfg.exclude_etf and i.is_etf:
            continue
        if cfg.min_list_days and i.list_date is not None \
                and (today - i.list_date).days < cfg.min_list_days:
            continue
        # 拿不到市值/成交额数据时不剔除
        if cap is not None and i.market_cap is not None and i.market_cap < cap:
            continue
        if turnover is not None and i.turnover is not None and i.turnover < turnover:
            continue
        out.append(i)
    return out
