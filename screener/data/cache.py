"""本地行情缓存（Parquet）与增量更新。股票只缓存日线，周线/月线由日线合成。"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pandas as pd

from .base import DataSource
from .timeframes import drop_unclosed, resample

# 股票市场收盘时间（当地时间）；当天日线在收盘后才算已收盘
MARKET_CLOSE = {
    "cn": ("Asia/Shanghai", "15:00"),
    "hk": ("Asia/Hong_Kong", "16:10"),
    "kr": ("Asia/Seoul", "15:30"),
    "us": ("America/New_York", "16:00"),
}
OVERLAP_BARS = 3  # 增量更新时重取最后几根，覆盖未收盘或复权变化


class Store:
    def __init__(self, root: str | Path = "data/cache"):
        self.root = Path(root)
        self.stale = False  # 上一次 update 是否因为取数失败而返回了旧缓存

    def _path(self, market: str, timeframe: str, symbol: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", symbol)
        return self.root / market / timeframe / f"{safe}.parquet"

    def update(self, src: DataSource, symbol: str, timeframe: str,
               max_age: float = 0, allow_stale: bool = False) -> pd.DataFrame:
        """max_age：缓存文件在这么多秒内更新过就直接用，不请求网络。
        allow_stale：请求失败时退回到已有缓存（self.stale 置为 True），用于画图；扫描不用。"""
        self.stale = False
        path = self._path(src.market, timeframe, symbol)
        cached = pd.read_parquet(path) if path.exists() else None
        if cached is not None and max_age > 0 and time.time() - path.stat().st_mtime < max_age:
            return cached
        since = cached.index[-OVERLAP_BARS] if cached is not None and len(cached) > OVERLAP_BARS else None
        try:
            new = src.fetch(symbol, timeframe, since=since)
        except Exception:
            if allow_stale and cached is not None and not cached.empty:
                self.stale = True
                return cached
            raise
        if cached is not None and not new.empty:
            df = pd.concat([cached[cached.index < new.index[0]], new])
        else:
            df = new if cached is None or not new.empty else cached
        df = df[~df.index.duplicated(keep="last")].sort_index()
        if not df.empty:
            path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(path)
        return df


def load_bars(store: Store, src: DataSource, symbol: str, timeframe: str,
              now: pd.Timestamp | None = None, max_age: float = 0,
              allow_stale: bool = False) -> pd.DataFrame:
    """返回只含已收盘 K 线的数据。max_age / allow_stale 见 Store.update。"""
    kw = {"max_age": max_age, "allow_stale": allow_stale}
    if src.market == "crypto":
        df = store.update(src, symbol, timeframe, **kw)
        return drop_unclosed(df, timeframe, now or pd.Timestamp.now(tz="UTC"))

    daily = store.update(src, symbol, "1d", **kw)
    tz, close = MARKET_CLOSE[src.market]
    local_now = (now or pd.Timestamp.now(tz="UTC")).tz_convert(tz).tz_localize(None)
    if not daily.empty and daily.index[-1].normalize() == local_now.normalize() \
            and local_now.strftime("%H:%M") < close:
        daily = daily.iloc[:-1]  # 今天还没收盘
    if timeframe == "1d":
        return daily
    return drop_unclosed(resample(daily, timeframe), timeframe, local_now)
