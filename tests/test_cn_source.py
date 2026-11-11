import pandas as pd

import screener.data.cn as cn


def test_tencent_code():
    assert cn._tencent_code("600519") == "sh600519"
    assert cn._tencent_code("688012") == "sh688012"
    assert cn._tencent_code("000538") == "sz000538"
    assert cn._tencent_code("300750") == "sz300750"
    assert cn._tencent_code("830799") == "bj830799"
    assert cn._tencent_code("920001") == "bj920001"


def test_falls_back_to_tencent_and_cools_down(monkeypatch):
    calls = []

    def em(symbol, since):
        calls.append("em")
        raise RuntimeError("Push2RateLimitError")

    def tx(symbol, since=None):
        calls.append("tx")
        return pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0]},
                            index=pd.DatetimeIndex(["2026-11-10"]))

    monkeypatch.setattr(cn, "_fetch_eastmoney", em)
    monkeypatch.setattr(cn, "fetch_tencent", tx)
    monkeypatch.setattr(cn, "_em_blocked_until", 0.0)
    src = cn.ChinaSource()
    assert len(src.fetch("000538")) == 1
    assert len(src.fetch("600519")) == 1
    # 第一次失败后进入冷却，第二次直接用腾讯，不再请求东方财富
    assert calls == ["em", "tx", "tx"]


class _Src:
    market = "crypto"

    def __init__(self, fail=False):
        self.fail, self.calls = fail, 0

    def fetch(self, symbol, timeframe, since=None):
        self.calls += 1
        if self.fail:
            raise RuntimeError("rate limited")
        return pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0]},
                            index=pd.DatetimeIndex(["2026-11-10"], tz="UTC"))


def test_store_cache_age_and_stale_fallback(tmp_path):
    from screener.data.cache import Store

    store = Store(tmp_path)
    src = _Src()
    store.update(src, "BTC/USDT", "1d")
    store.update(src, "BTC/USDT", "1d", max_age=600)  # 刚更新过：不请求
    assert src.calls == 1
    failing = _Src(fail=True)
    df = store.update(failing, "BTC/USDT", "1d", allow_stale=True)  # 失败 → 用旧缓存
    assert len(df) == 1 and store.stale
    try:
        store.update(failing, "BTC/USDT", "1d")  # 扫描不允许旧数据
        raise AssertionError("should raise")
    except RuntimeError:
        pass
