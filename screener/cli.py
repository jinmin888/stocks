"""命令行扫描：python -m screener.cli --market crypto --timeframe 4h --universe top100"""

from __future__ import annotations

import argparse
import sys

import pandas as pd
import yaml

from .config import ScreenConfig
from .runner import ScanRequest, display_time, run_scan, too_new  # noqa: F401  (re-export)


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
    p.add_argument("--retry-wait", type=int, default=300, help="失败标的重试前等待秒数，0 为不重试")
    a = p.parse_args(argv)

    cfg = ScreenConfig.model_validate(yaml.safe_load(open(a.config)) or {}) if a.config else ScreenConfig()
    req = ScanRequest(market=a.market, timeframe=a.timeframe, universe=a.universe,
                      symbols=a.symbols or [], exchange=a.exchange)

    def progress(done, total, msg):
        if msg:
            print(f"  {msg}", file=sys.stderr)
        elif done % 100 == 0:
            print(f"  {done}/{total}", file=sys.stderr)

    try:
        res = run_scan(req, cfg, a.cache, a.retry_wait, progress)
    except (RuntimeError, NotImplementedError, ValueError) as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
    if res.failed:
        print(f"注意：{len(res.failed)} 个标的未取到数据：{' '.join(res.failed)}", file=sys.stderr)

    out = pd.DataFrame(res.rows)
    if out.empty:
        print("没有符合条件的标的")
        return 0
    with pd.option_context("display.max_rows", None, "display.width", 200):
        print(out.to_string(index=False))
    if a.csv:
        out.to_csv(a.csv, index=False, encoding="utf-8-sig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
