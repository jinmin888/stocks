"""FastAPI 应用：登录、扫描任务、运行记录、结果、K 线图数据。

启动：uvicorn server.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import hmac
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from sqlmodel import func, select
from starlette.middleware.sessions import SessionMiddleware

from screener.config import ScreenConfig
from screener.data.cache import Store, load_bars
from screener.data.registry import DEFAULT_UNIVERSE
from screener.runner import ScanRequest, source_for
from screener.screen import analyze

from . import db, jobs
from .settings import settings

MARKETS = {
    "crypto": {"timeframes": ["15m", "1h", "4h", "1d", "1w", "1M"],
               "universes": ["top50", "top100", "top200", "all"], "exchanges": ["binance", "okx"]},
    "kr": {"timeframes": ["1d", "1w", "1M"],
           "universes": ["all", "kospi", "kosdaq", "kospi200", "kosdaq150"]},
    "cn": {"timeframes": ["1d", "1w", "1M"],
           "universes": ["all", "csi300", "csi500", "csi1000", "sse50"]},
    "us": {"timeframes": ["1d", "1w", "1M"], "universes": ["sp500", "all"]},
    "hk": {"timeframes": ["1d", "1w", "1M"], "universes": ["hsi"]},
}
# 建议的定时（收盘后），前端新建任务时作为默认值
DEFAULT_SCHEDULE = {
    "cn": ("40 15 * * 1-5", "Asia/Shanghai"),
    "hk": ("40 16 * * 1-5", "Asia/Hong_Kong"),
    "kr": ("10 16 * * 1-5", "Asia/Seoul"),
    "us": ("20 16 * * 1-5", "America/New_York"),
    "crypto:15m": ("*/15 * * * *", "UTC"),
    "crypto:1h": ("2 * * * *", "UTC"),
    "crypto:4h": ("3 */4 * * *", "UTC"),
    "crypto:1d": ("5 0 * * *", "UTC"),
    "crypto:1w": ("10 0 * * 1", "UTC"),
    "crypto:1M": ("15 0 1 * *", "UTC"),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if db.engine is None:
        db.init_db()
    jobs.start()
    yield
    jobs.stop()


app = FastAPI(title="Stock Screener", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, same_site="lax",
                   https_only=settings.https_only, max_age=30 * 24 * 3600)


@app.get("/api/health", include_in_schema=False)
def health():
    return {"ok": True}


# ---------------------------------------------------------------- 登录

class LoginBody(BaseModel):
    username: str
    password: str


def require_user(request: Request) -> str:
    user = request.session.get("user")
    if not user:
        raise HTTPException(401, "未登录")
    return user


@app.post("/api/login")
async def login(body: LoginBody, request: Request):
    ok = bool(settings.password) and hmac.compare_digest(body.username, settings.username) \
        and hmac.compare_digest(body.password, settings.password)
    if not ok:
        await asyncio.sleep(1)  # 减缓暴力尝试
        raise HTTPException(401, "账号或密码错误")
    request.session["user"] = body.username
    return {"user": body.username}


@app.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/me")
def me(user: str = Depends(require_user)):
    return {"user": user}


# ---------------------------------------------------------------- 元数据

@app.get("/api/meta")
def meta(_: str = Depends(require_user)):
    return {
        "markets": MARKETS,
        "default_universe": DEFAULT_UNIVERSE,
        "default_schedule": {k: {"cron": c, "timezone": tz} for k, (c, tz) in DEFAULT_SCHEDULE.items()},
        "default_config": ScreenConfig().model_dump(mode="json"),
    }


# ---------------------------------------------------------------- 扫描任务

class TaskBody(BaseModel):
    name: str
    markets: List[str]
    universes: Dict[str, Optional[str]] = {}
    symbols_by_market: Dict[str, List[str]] = {}
    timeframe: str = "1d"
    exchange: str = "binance"
    config: dict = {}
    cron: Optional[str] = None
    timezone: str = "Asia/Seoul"
    enabled: bool = True
    notify: bool = True

    @field_validator("cron")
    @classmethod
    def _cron(cls, v):
        if v in (None, ""):
            return None
        from apscheduler.triggers.cron import CronTrigger
        try:
            CronTrigger.from_crontab(v)
        except ValueError as e:
            raise ValueError(f"定时表达式无效：{e}")
        return v

    def fields(self) -> dict:
        """写入数据库的字段；旧版单市场字段填第一个市场，保持兼容。"""
        d = self.model_dump()
        first = self.markets[0]
        d.update(market=first, universe=self.universes.get(first), symbols=self.symbols_by_market.get(first, []))
        return d

    def check(self) -> None:
        if not self.markets:
            raise HTTPException(422, "至少选择一个市场")
        for market in self.markets:
            m = MARKETS.get(market)
            if m is None:
                raise HTTPException(422, f"未知市场：{market}")
            if self.timeframe not in m["timeframes"]:
                raise HTTPException(422, f"{market} 支持的周期：{m['timeframes']}")
        # 只保留已选市场的设置
        self.markets = list(dict.fromkeys(self.markets))
        self.universes = {m: self.universes.get(m) or DEFAULT_UNIVERSE[m] for m in self.markets}
        self.symbols_by_market = {m: self.symbols_by_market.get(m) or [] for m in self.markets}
        try:
            ScreenConfig.model_validate(self.config)
        except Exception as e:
            raise HTTPException(422, f"条件配置无效：{e}")


def _task_out(t: db.Task, s) -> dict:
    last = s.exec(select(db.Run).where(db.Run.task_id == t.id)
                  .order_by(db.Run.id.desc())).first()
    nr = jobs.next_run(t.id)
    return {**t.model_dump(mode="json"),
            "config": ScreenConfig.model_validate(t.config).model_dump(mode="json"),
            "last_run": _run_out(last, s) if last else None,
            "next_run": nr.isoformat() if nr else None}


@app.get("/api/tasks")
def list_tasks(_: str = Depends(require_user)):
    with db.session() as s:
        return [_task_out(t, s) for t in s.exec(select(db.Task).order_by(db.Task.id)).all()]


@app.post("/api/tasks")
def create_task(body: TaskBody, _: str = Depends(require_user)):
    body.check()
    with db.session() as s:
        t = db.Task(**body.fields())
        s.add(t)
        s.commit()
        s.refresh(t)
        jobs.sync_task(t)
        return _task_out(t, s)


@app.get("/api/tasks/{task_id}")
def get_task(task_id: int, _: str = Depends(require_user)):
    with db.session() as s:
        t = s.get(db.Task, task_id) or _404()
        return _task_out(t, s)


@app.put("/api/tasks/{task_id}")
def update_task(task_id: int, body: TaskBody, _: str = Depends(require_user)):
    body.check()
    with db.session() as s:
        t = s.get(db.Task, task_id) or _404()
        for k, v in body.fields().items():
            setattr(t, k, v)
        t.updated_at = db.now()
        s.add(t)
        s.commit()
        s.refresh(t)
        jobs.sync_task(t)
        return _task_out(t, s)


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int, _: str = Depends(require_user)):
    with db.session() as s:
        t = s.get(db.Task, task_id) or _404()
        s.delete(t)
        s.commit()
    jobs.remove_task(task_id)
    return {"ok": True}


@app.post("/api/tasks/{task_id}/run")
def run_task(task_id: int, _: str = Depends(require_user)):
    run_id = jobs.enqueue(task_id)
    if run_id is None:
        _404()
    return {"run_id": run_id}


# ---------------------------------------------------------------- 运行记录与结果

def _run_out(r: db.Run, s) -> dict:
    n = s.exec(select(func.count()).select_from(db.Result).where(db.Result.run_id == r.id)).one()
    out = r.model_dump(mode="json", exclude={"snapshot"})
    out["result_count"] = n
    out["task_name"] = (r.snapshot or {}).get("name")
    out["markets"] = [m for m, _, _ in db.task_markets(r.snapshot or {})]
    out["timeframe"] = (r.snapshot or {}).get("timeframe")
    return out


@app.get("/api/runs")
def list_runs(task_id: Optional[int] = None, limit: int = 50, _: str = Depends(require_user)):
    with db.session() as s:
        q = select(db.Run).order_by(db.Run.id.desc()).limit(min(limit, 200))
        if task_id is not None:
            q = q.where(db.Run.task_id == task_id)
        return [_run_out(r, s) for r in s.exec(q).all()]


@app.get("/api/runs/{run_id}")
def get_run(run_id: int, _: str = Depends(require_user)):
    with db.session() as s:
        r = s.get(db.Run, run_id) or _404()
        results = s.exec(select(db.Result).where(db.Result.run_id == run_id)).all()
        return {**_run_out(r, s), "snapshot": r.snapshot,
                "results": [x.model_dump(exclude={"run_id"}) for x in results]}


# ---------------------------------------------------------------- 按日期查看信号

def _done_results(s, date_prefix: Optional[str] = None):
    q = (select(db.Result, db.Run).join(db.Run, db.Run.id == db.Result.run_id)
         .where(db.Run.status == "done"))
    if date_prefix:
        q = q.where(db.Result.date.startswith(date_prefix))
    return s.exec(q).all()


@app.get("/api/signals/dates")
def signal_dates(limit: int = 120, _: str = Depends(require_user)):
    """有信号的日期（信号 K 线的日期，加密货币为 KST 收盘日期），新的在前。"""
    with db.session() as s:
        seen: Dict[str, set] = {}
        for res, run in _done_results(s):
            key = (res.market or db.task_markets(run.snapshot or {})[0][0], res.symbol, res.side,
                   (run.snapshot or {}).get("timeframe"))
            seen.setdefault(res.date[:10], set()).add(key)
    days = sorted(seen.items(), key=lambda kv: kv[0], reverse=True)[: min(limit, 1000)]
    out = []
    for d, keys in days:
        out.append({"date": d, "count": len(keys),
                    "bottom": sum(1 for k in keys if k[2] == "bottom"),
                    "top": sum(1 for k in keys if k[2] == "top")})
    return out


@app.get("/api/signals")
def signals(date: str, _: str = Depends(require_user)):
    """某一天的全部信号；同一标的同方向同周期被多次扫出时只保留最新一次，并列出来源任务。"""
    if len(date) != 10:
        raise HTTPException(422, "date 格式：YYYY-MM-DD")
    with db.session() as s:
        rows: Dict[tuple, dict] = {}
        for res, run in _done_results(s, date):
            snap = run.snapshot or {}
            market = res.market or db.task_markets(snap)[0][0]
            tf = snap.get("timeframe")
            key = (market, res.symbol, res.side, tf)
            task = snap.get("name")
            cur = rows.get(key)
            if cur is None or run.id > cur["run_id"]:
                tasks = cur["tasks"] if cur else []
                cur = {**res.model_dump(exclude={"run_id"}), "market": market, "timeframe": tf,
                       "run_id": run.id, "tasks": tasks,
                       "found_at": (run.finished_at or run.created_at).isoformat()}
                rows[key] = cur
            if task and task not in cur["tasks"]:
                cur["tasks"].append(task)
    return sorted(rows.values(), key=lambda r: (r["side"], -(r["divergence_score"] or -1), r["symbol"]))


# ---------------------------------------------------------------- K 线图

def _ts(t: pd.Timestamp) -> int:
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return int(t.timestamp())


@app.get("/api/chart")
def chart(market: str, symbol: str, timeframe: str = "1d", run_id: Optional[int] = None,
          exchange: str = "binance", bars: int = 300, _: str = Depends(require_user)):
    cfg = ScreenConfig()
    if run_id is not None:
        with db.session() as s:
            r = s.get(db.Run, run_id) or _404()
            snap = r.snapshot or {}
            cfg = ScreenConfig.model_validate(snap.get("config") or {})
            exchange = snap.get("exchange", exchange)
    src = source_for(ScanRequest(market=market, exchange=exchange), settings.cache_dir)
    try:
        df = load_bars(Store(settings.cache_dir), src, symbol, timeframe)
    except Exception as e:
        raise HTTPException(502, f"取数据失败：{type(e).__name__} {e}")
    if df.empty:
        raise HTTPException(404, "没有数据")
    # 在完整历史上计算（RSI 需要预热），只返回最后 N 根
    a = analyze(df, cfg)
    start = max(0, len(df) - min(bars, 2000))
    times = [_ts(t) for t in df.index]

    def point(f):
        return {"time": times[f.extreme_pos], "price": f.price}

    return {
        "symbol": symbol, "market": market, "timeframe": timeframe,
        "bars": [{"time": times[i], "open": r.open, "high": r.high, "low": r.low,
                  "close": r.close, "volume": r.volume}
                 for i, r in enumerate(df.itertuples()) if i >= start],
        "rsi": [{"time": times[i], "value": round(float(v), 2)}
                for i, v in enumerate(a["rsi"]) if i >= start and pd.notna(v)],
        "fractals": [{**point(f), "type": f.type, "strength": f.strength.name.lower(),
                      "confirm_time": times[f.end]}
                     for f in a["fractals"] if f.extreme_pos >= start],
        "divergences": [{"side": d.side, "kind": d.kind, "score": round(d.score, 2),
                         "from": {**point(d.first), "rsi": round(d.r1, 2)},
                         "to": {**point(d.second), "rsi": round(d.r2, 2)}}
                        for d in a["divergences"] if d.first.extreme_pos >= start],
        "config": {"rsi_period": cfg.divergence.rsi_period,
                   "oversold": cfg.divergence.oversold, "overbought": cfg.divergence.overbought},
    }


def _404():
    raise HTTPException(404, "不存在")


from . import notify  # noqa: E402  注册 KakaoTalk 路由与通知回调

app.include_router(notify.router)


# ---------------------------------------------------------------- 前端静态文件

WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = WEB_DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(WEB_DIST / "index.html")
