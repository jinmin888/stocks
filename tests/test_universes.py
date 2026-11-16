import pandas as pd
import pytest

import screener.data.universes as u
from screener.data.base import Instrument


def test_cached_falls_back_to_last_good_list(tmp_path):
    good = [Instrument(symbol="600519", market="cn")]
    folder = tmp_path / "universe"
    folder.mkdir()
    (folder / "cn_csi300_20261101.json").write_text('[{"symbol": "000001", "market": "cn"}]')

    def boom():
        raise ConnectionError("Failed to resolve 'oss-ch.csindex.com.cn'")

    assert [i.symbol for i in u.cached(tmp_path, "cn_csi300", boom)] == ["000001"]
    # 成功后写入今天的文件并删除旧文件
    assert [i.symbol for i in u.cached(tmp_path, "cn_csi300", lambda: good)] == ["600519"]
    assert [p.name for p in folder.iterdir()] == [f"cn_csi300_{pd.Timestamp.today():%Y%m%d}.json"]


def _unreachable():
    raise ConnectionError("[Errno 101] Network is unreachable")


def test_cached_uses_bundled_snapshot_on_first_run(tmp_path):
    u.notices.clear()
    for key, n in (("cn_csi300", 300), ("cn_csi500", 500), ("cn_csi1000", 1000), ("cn_sse50", 50)):
        items = u.cached(tmp_path, key, _unreachable)
        assert len(items) == n and all(len(i.symbol) == 6 and i.market == "cn" for i in items)
    assert len(u.notices) == 4 and "内置快照" in u.notices[0]
    assert not (tmp_path / "universe").exists()  # 快照不写入缓存，下次仍会尝试在线获取
    u.notices.clear()


def test_cached_raises_without_any_list(tmp_path):
    with pytest.raises(ConnectionError):
        u.cached(tmp_path, "us_sp500", _unreachable)  # 没有内置快照的列表


def _dns_fail(symbol):
    raise ConnectionError("Failed to resolve 'oss-ch.csindex.com.cn'")


def test_csindex_uses_sina_when_official_fails(monkeypatch):
    import akshare as ak

    monkeypatch.setattr(ak, "index_stock_cons_csindex", _dns_fail)
    rows = pd.DataFrame({"code": [f"{i:06d}" for i in range(1, 51)], "name": ["*ST测试"] + ["x"] * 49})
    monkeypatch.setattr(ak, "index_stock_cons_sina", lambda symbol: rows)
    items = u.csindex("000016")  # 上证50：50 只
    assert len(items) == 50 and items[0].symbol == "000001" and items[0].is_st


def test_csindex_rejects_incomplete_fallback(monkeypatch):
    import akshare as ak

    monkeypatch.setattr(ak, "index_stock_cons_csindex", _dns_fail)
    monkeypatch.setattr(ak, "index_stock_cons_sina",
                        lambda symbol: pd.DataFrame({"code": ["600519"] * 10, "name": ["贵州茅台"] * 10}))
    with pytest.raises(RuntimeError, match="000905"):
        u.csindex("000905")  # 中证500 只拿到 1 只：拒绝
    monkeypatch.setattr(ak, "index_stock_cons_sina", lambda symbol: pd.DataFrame())
    with pytest.raises(RuntimeError, match="000852"):
        u.csindex("000852")  # 新浪没有中证1000
