import pandas as pd


def bars(rows, volumes=None):
    """rows: [(open, high, low, close), ...]"""
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"],
                      index=pd.date_range("2026-01-01", periods=len(rows), freq="D"))
    df["volume"] = volumes if volumes is not None else 100.0
    return df


def from_closes(closes, wick=0.3):
    """由收盘价路径生成 K 线：开盘=前收，高低在实体外加 wick。"""
    rows = []
    prev = closes[0]
    for c in closes:
        o = prev
        rows.append((o, max(o, c) + wick, min(o, c) - wick, c))
        prev = c
    return bars(rows)
