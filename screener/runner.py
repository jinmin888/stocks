"""一次完整扫描：取范围 → 过滤 → 逐个取 K 线并筛选 → 失败重试。命令行和网站共用。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import pandas as pd

from . import filters
from .config import ScreenConfig
from .data import get_source
from .data.base import Instrument
from .data.cache import Store, load_bars
from .data.registry import DEFAULT_UNIVERSE
from .data.timeframes import bar_end
from .screen import screen

Progress = Callable[[int, int, str], None]  # (done, total, message)


@dataclass
class ScanRequest:
    market: str
    timeframe: str = "1d"
    universe: Optional[str] = None
    symbols: List[str] = field(default_factory=list)
    exchange: str = "binance"


@dataclass
class ScanOutcome:
    total: int
    rows: List[dict]
    failed: List[str]


def display_time(start: pd.Timestamp, market: str, timeframe: str, tz: str) -> str:
    """加密货币：显示 K 线收盘时刻（display_tz）；股票：显示当地交易日期（周/月线为起始日）。"""
    if market == "crypto":
        end = bar_end(start, timeframe).tz_convert(tz)
        return end.strftime("%Y-%m-%d %H:%M")
    return start.strftime("%Y-%m-%d")


def too_new(df: pd.DataFrame, market: str, min_days) -> bool:
    """股票：历史 K 线不足 min_days 天视为上市不满 N 天（缓存会取约 2 年历史）。"""
    if market == "crypto" or not min_days or df.empty:
        return False
    first = df.index[0].tz_localize(None) if df.index.tz else df.index[0]
    return (pd.Timestamp.today() - first).days < min_days


def source_for(req: ScanRequest, cache_root: str):
    if req.market == "crypto":
        return get_source("crypto", cache_root, exchange=req.exchange)
    return get_source(req.market, cache_root)


def resolve_universe(req: ScanRequest, cfg: ScreenConfig, src) -> List[Instrument]:
    if req.symbols:
        insts = src.instruments(req.symbols)
    else:
        insts = src.universe(req.universe or DEFAULT_UNIVERSE[req.market])
    insts = filters.apply(insts, req.market, cfg.filters)
    if req.market == "crypto" and not req.symbols:
        uni = req.universe or DEFAULT_UNIVERSE["crypto"]
        if uni.startswith("top"):
            insts = insts[: int(uni[3:] or 100)]
    return insts


def run_scan(req: ScanRequest, cfg: ScreenConfig, cache_root: str = "data/cache",
             retry_wait: int = 300, progress: Optional[Progress] = None) -> ScanOutcome:
    """可能抛出 ValueError / RuntimeError（范围不可用、缺少 KRX 账号等）。"""
    src = source_for(req, cache_root)
    if req.timeframe not in src.timeframes:
        raise ValueError(f"{req.market} 支持的周期：{src.timeframes}")
    insts = resolve_universe(req, cfg, src)
    store, rows = Store(cache_root), []
    report = progress or (lambda *_: None)

    def run(batch: List[Instrument]) -> List[Instrument]:
        failed = []
        for n, inst in enumerate(batch, 1):
            try:
                df = load_bars(store, src, inst.symbol, req.timeframe)
                if not too_new(df, req.market, cfg.filters.min_list_days):
                    for sig in screen(df, cfg):
                        row = sig.to_row()
                        row["date"] = display_time(row["date"], req.market, req.timeframe,
                                                   cfg.display_tz)
                        rows.append({"symbol": inst.symbol, "name": inst.name, **row})
            except Exception as e:  # 单个标的失败不影响整体
                failed.append(inst)
                report(n, len(batch), f"{inst.symbol}: {type(e).__name__} {str(e)[:120]}")
            if n % 20 == 0 or n == len(batch):
                report(n, len(batch), "")
            if req.market == "cn":
                time.sleep(0.3)  # 东方财富限流
        return failed

    report(0, len(insts), f"扫描 {len(insts)} 个标的 · {req.market} {req.timeframe}")
    failed = run(insts)
    if failed and retry_wait > 0:
        report(0, len(failed), f"{len(failed)} 个标的失败，{retry_wait} 秒后重试")
        time.sleep(retry_wait)
        failed = run(failed)
    rows.sort(key=lambda r: (r["side"], -(r["divergence_score"] or -1)))
    return ScanOutcome(total=len(insts), rows=rows, failed=[i.symbol for i in failed])
