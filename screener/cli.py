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
from .data.cache import Store, load_bars
from .screen import screen


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="顶底分型 + RSI 背离筛选")
    p.add_argument("--market", required=True, choices=["crypto", "cn", "hk", "us", "kr"])
    p.add_argument("--timeframe", default="1d")
    p.add_argument("--universe", help="crypto: topN / all；cn: all")
    p.add_argument("--symbols", nargs="*", help="自定义列表")
    p.add_argument("--exchange", default="binance", help="加密货币交易所")
    p.add_argument("--config", help="YAML 配置文件")
    p.add_argument("--csv", help="结果导出 CSV 路径")
    p.add_argument("--cache", default="data/cache")
    a = p.parse_args(argv)

    cfg = ScreenConfig.model_validate(yaml.safe_load(open(a.config)) or {}) if a.config else ScreenConfig()
    src = get_source(a.market, exchange=a.exchange) if a.market == "crypto" else get_source(a.market)
    if a.timeframe not in src.timeframes:
        p.error(f"{a.market} 支持的周期：{src.timeframes}")

    if a.symbols:
        insts = src.instruments(a.symbols)
    else:
        insts = src.universe(a.universe or ("top100" if a.market == "crypto" else "all"))
    insts = filters.apply(insts, a.market, cfg.filters)
    print(f"扫描 {len(insts)} 个标的 · {a.market} {a.timeframe}", file=sys.stderr)

    store, rows = Store(a.cache), []
    for n, inst in enumerate(insts, 1):
        try:
            df = load_bars(store, src, inst.symbol, a.timeframe)
            for sig in screen(df, cfg):
                rows.append({"symbol": inst.symbol, "name": inst.name, **sig.to_row()})
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
