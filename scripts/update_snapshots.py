"""更新内置的指数成分股快照（screener/data/snapshots/）。

快照是最后的兜底：当官方来源、备用来源和本地缓存都不可用时使用。
中证指数每年 6 月、12 月调整成分，调整后运行一次：python scripts/update_snapshots.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import akshare as ak

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from screener.data import universes as u  # noqa: E402

OUT = Path(u.__file__).parent / "snapshots"


def main() -> int:
    OUT.mkdir(exist_ok=True)
    failed = []
    for name, code in u.CSINDEX.items():
        for attempt in range(4):
            try:
                df = ak.index_stock_cons_csindex(symbol=code)
                break
            except Exception as e:
                print(f"{name}: {type(e).__name__}，重试 {attempt + 1}/4", file=sys.stderr)
                time.sleep(5 * (attempt + 1))
        else:
            failed.append(name)
            continue
        items = [{"symbol": str(c).zfill(6), "name": str(n)}
                 for c, n in zip(df["成分券代码"], df["成分券名称"])]
        if len(items) != u.CSINDEX_SIZE[code]:
            print(f"{name}: 成分数量 {len(items)} 不符，跳过", file=sys.stderr)
            failed.append(name)
            continue
        as_of = str(df["日期"].iloc[0])[:10]
        (OUT / f"cn_{name}.json").write_text(json.dumps(
            {"as_of": as_of, "source": "csindex.com.cn", "items": items},
            ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"{name}: {len(items)} 只，{as_of}")
    if failed:
        print(f"未更新：{failed}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
