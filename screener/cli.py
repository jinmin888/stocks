"""命令行扫描：python -m screener.cli --market crypto --timeframe 4h --universe top100"""

from __future__ import annotations

import argparse
import sys
import time

import pandas as pd
import yaml

from . import filters
from .config import ScreenConfig
from .data import get_source
from .data.registry import DEFAULT_UNIVERSE
from .data.cache import Store, load_bars
from .data.timeframes import bar_end
from .screen import screen


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


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="顶底分型 + RSI 背离筛选")
    p.add_argument("--market", required=True, choices=["crypto", "cn", "hk", "us", "kr"])
    p.add_argument("--timeframe", default="1d")
    p.add_argument("--universe", help=(
        "crypto: topN / all；us: sp500 / all；hk: hsi；"
        "cn: all / csi300 / csi500 / csi1000 / sse50；kr: all / kospi / kosdaq / kospi200 / kosdaq150"))
    p.add_argument("--symbols", nargs="*", help="自定义列表")
    p.add_argument("--exchange", default="binance", help="加密货币交易所")
    p.add_argument("--config", help="YAML 配置文件")
    p.add_argument("--csv", help="结果导出 CSV 路径")
    p.add_argument("--cache", default="data/cache")
    a = p.parse_args(argv)

    cfg = ScreenConfig.model_validate(yaml.safe_load(open(a.config)) or {}) if a.config else ScreenConfig()
    src = get_source(a.market, a.cache, exchange=a.exchange) if a.market == "crypto" \
        else get_source(a.market, a.cache)
    if a.timeframe not in src.timeframes:
        p.error(f"{a.market} 支持的周期：{src.timeframes}")

    if a.symbols:
        insts = src.instruments(a.symbols)
    else:
        try:
            insts = src.universe(a.universe or DEFAULT_UNIVERSE[a.market])
        except (RuntimeError, NotImplementedError, ValueError) as e:
            print(f"错误：{e}", file=sys.stderr)
            return 2
    insts = filters.apply(insts, a.market, cfg.filters)
    if a.market == "crypto" and not a.symbols:
        uni = a.universe or "top100"
        if uni.startswith("top"):
            insts = insts[: int(uni[3:] or 100)]
    print(f"扫描 {len(insts)} 个标的 · {a.market} {a.timeframe}", file=sys.stderr)

    store, rows = Store(a.cache), []
    for n, inst in enumerate(insts, 1):
        try:
            df = load_bars(store, src, inst.symbol, a.timeframe)
            if too_new(df, a.market, cfg.filters.min_list_days):
                continue
            for sig in screen(df, cfg):
                row = sig.to_row()
                row["date"] = display_time(row["date"], a.market, a.timeframe, cfg.display_tz)
                rows.append({"symbol": inst.symbol, "name": inst.name, **row})
        except Exception as e:  # 单个标的失败不影响整体
            print(f"  {inst.symbol}: {type(e).__name__} {str(e)[:120]}", file=sys.stderr)
        if n % 50 == 0:
            print(f"  {n}/{len(insts)}", file=sys.stderr)
        if a.market == "cn":
            time.sleep(0.3)  # 东方财富限流

    out = pd.DataFrame(rows)
    if out.empty:
        print("没有符合条件的标的")
        return 0
    out = out.sort_values(["side", "divergence_score"], ascending=[True, False], na_position="last")
    with pd.option_context("display.max_rows", None, "display.width", 200):
        print(out.to_string(index=False))
    if a.csv:
        out.to_csv(a.csv, index=False, encoding="utf-8-sig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
