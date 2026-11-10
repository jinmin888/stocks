import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from pathlib import Path

    import server.db as db
    import server.jobs as jobs
    import server.main as main
    from server.settings import settings

    monkeypatch.setattr(settings, "password", "pw")
    monkeypatch.setattr(settings, "data_dir", Path(tmp_path))
    monkeypatch.setattr(settings, "enable_scheduler", False)

    from screener.runner import ScanOutcome

    def fake_scan(req, cfg, cache, retry, progress):
        progress(1, 2, "")
        return ScanOutcome(total=2, rows=[{
            "symbol": "BTC/USDT", "name": "BTC", "side": "bottom", "date": "2026-11-10 17:00",
            "close": 1.0, "rsi": 30.0, "fractal_strength": "strong", "divergence": "regular",
            "divergence_score": 12.0, "price_change_pct": 1.0, "rsi_diff": 11.8}], failed=["X/USDT"])

    monkeypatch.setattr(jobs, "run_scan", fake_scan)
    db.init_db()
    with TestClient(main.app) as c:
        yield c


def login(c):
    assert c.post("/api/login", json={"username": "admin", "password": "pw"}).status_code == 200


def test_auth_required(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.post("/api/login", json={"username": "admin", "password": "no"}).status_code == 401
    login(client)
    assert client.get("/api/me").json() == {"user": "admin"}


def test_task_crud_and_run(client):
    login(client)
    body = {"name": "BTC 4h", "markets": ["crypto"], "timeframe": "4h", "universes": {"crypto": "top100"},
            "cron": "3 */4 * * *", "timezone": "UTC",
            "config": {"logic": "or", "divergence": {"hidden": True}}}
    t = client.post("/api/tasks", json=body).json()
    assert t["config"]["divergence"]["hidden"] is True
    assert t["config"]["divergence"]["rsi_period"] == 14  # 默认值补全

    bad = client.post("/api/tasks", json={**body, "timeframe": "15m", "markets": ["us"]})
    assert bad.status_code == 422
    # 多市场时周期必须所有市场都支持
    assert client.post("/api/tasks", json={**body, "markets": ["crypto", "us"]}).status_code == 422
    assert client.post("/api/tasks", json={**body, "markets": []}).status_code == 422
    assert client.post("/api/tasks", json={**body, "cron": "nope"}).status_code == 422

    run_id = client.post(f"/api/tasks/{t['id']}/run").json()["run_id"]
    for _ in range(50):
        r = client.get(f"/api/runs/{run_id}").json()
        if r["status"] in ("done", "failed"):
            break
        time.sleep(0.05)
    assert r["status"] == "done", r
    assert r["failed"] == ["X/USDT"]
    assert r["results"][0]["symbol"] == "BTC/USDT"
    assert client.get("/api/tasks").json()[0]["last_run"]["result_count"] == 1

    upd = client.put(f"/api/tasks/{t['id']}", json={**body, "name": "renamed"}).json()
    assert upd["name"] == "renamed"
    # 运行快照保留当时的名称
    assert client.get(f"/api/runs/{run_id}").json()["task_name"] == "BTC 4h"
    assert client.delete(f"/api/tasks/{t['id']}").status_code == 200
    assert client.get("/api/tasks").json() == []


def test_meta(client):
    login(client)
    m = client.get("/api/meta").json()
    assert "crypto" in m["markets"] and m["default_config"]["fractal"]["inclusion"] is True


def test_multi_market_run(client):
    login(client)
    body = {"name": "多市场", "markets": ["us", "hk"], "timeframe": "1d",
            "symbols_by_market": {"us": ["AAPL"], "crypto": ["BTC/USDT"]}}
    t = client.post("/api/tasks", json=body).json()
    assert t["markets"] == ["us", "hk"]
    assert t["universes"] == {"us": "sp500", "hk": "hsi"}  # 未指定时用默认范围
    assert t["symbols_by_market"] == {"us": ["AAPL"], "hk": []}  # 未选市场的设置被丢弃
    run_id = client.post(f"/api/tasks/{t['id']}/run").json()["run_id"]
    for _ in range(50):
        r = client.get(f"/api/runs/{run_id}").json()
        if r["status"] in ("done", "failed"):
            break
        time.sleep(0.05)
    assert r["status"] == "done", r
    assert r["markets"] == ["us", "hk"]
    assert sorted(x["market"] for x in r["results"]) == ["hk", "us"]
    assert r["total"] == 4 and sorted(r["failed"]) == ["hk:X/USDT", "us:X/USDT"]


def test_migrates_legacy_single_market_task(tmp_path):
    import sqlite3

    from sqlmodel import select

    import server.db as db

    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE task (id INTEGER PRIMARY KEY, name VARCHAR, market VARCHAR, timeframe VARCHAR,"
        " universe VARCHAR, symbols JSON, exchange VARCHAR, config JSON, cron VARCHAR, timezone VARCHAR,"
        " enabled BOOLEAN, notify BOOLEAN, created_at DATETIME, updated_at DATETIME);"
        "INSERT INTO task VALUES (1,'old','cn','1d','csi300','[\"600519\"]','binance','{}',NULL,"
        "'Asia/Seoul',1,1,'2026-01-01','2026-01-01');"
        "CREATE TABLE result (id INTEGER PRIMARY KEY, run_id INTEGER, symbol VARCHAR, name VARCHAR,"
        " side VARCHAR, date VARCHAR, close FLOAT, rsi FLOAT, fractal_strength VARCHAR, divergence VARCHAR,"
        " divergence_score FLOAT, price_change_pct FLOAT, rsi_diff FLOAT);")
    con.commit()
    con.close()
    eng = db.init_db(f"sqlite:///{path}")
    with db.Session(eng) as s:
        t = s.exec(select(db.Task)).one()
    assert t.markets == ["cn"] and t.universes == {"cn": "csi300"}
    assert t.symbols_by_market == {"cn": ["600519"]}
