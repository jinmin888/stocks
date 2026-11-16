from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import JSON, Column, inspect, text
from sqlmodel import Field, Session, SQLModel, create_engine, select

from .settings import settings


def now() -> datetime:
    return datetime.now(timezone.utc)


class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    # 可选择多个市场；每个市场单独设置扫描范围和自定义列表，周期 / 条件 / 定时共用
    markets: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    universes: Dict[str, Optional[str]] = Field(default_factory=dict, sa_column=Column(JSON))
    symbols_by_market: Dict[str, List[str]] = Field(default_factory=dict, sa_column=Column(JSON))
    # 旧版单市场字段：保留以兼容已有数据，新代码通过 task_markets() 读取
    market: str = ""
    universe: Optional[str] = None
    symbols: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    timeframe: str = "1d"
    exchange: str = "binance"
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))  # ScreenConfig
    cron: Optional[str] = None  # 定时表达式；None 为仅手动
    timezone: str = "Asia/Seoul"
    enabled: bool = True
    notify: bool = True
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class Run(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: Optional[int] = Field(default=None, index=True)
    trigger: str = "manual"  # manual / schedule
    status: str = "queued"  # queued / running / done / failed
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    total: int = 0
    done: int = 0
    message: str = ""
    error: Optional[str] = None
    failed: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    # 运行时的任务快照，任务之后被修改也能看到当时的条件
    snapshot: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now)


class Result(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(index=True)
    market: str = ""
    symbol: str
    name: str = ""
    side: str
    date: str
    close: float
    rsi: Optional[float] = None
    fractal_strength: Optional[str] = None
    divergence: Optional[str] = None
    divergence_score: Optional[float] = None
    price_change_pct: Optional[float] = None
    rsi_diff: Optional[float] = None


class KakaoToken(SQLModel, table=True):
    """KakaoTalk「나에게 보내기」的 OAuth 令牌（单用户，只有一行）。"""
    id: int = Field(default=1, primary_key=True)
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=now)


engine = None


def task_markets(t: dict) -> List[tuple]:
    """[(market, universe, symbols), ...]；兼容旧版单市场任务和运行快照。"""
    markets = t.get("markets") or ([t["market"]] if t.get("market") else [])
    universes = t.get("universes") or {}
    symbols = t.get("symbols_by_market") or {}
    if not t.get("markets") and t.get("market"):
        universes = {t["market"]: t.get("universe")}
        symbols = {t["market"]: t.get("symbols") or []}
    return [(m, universes.get(m), symbols.get(m) or []) for m in markets]


# 已有数据库缺少的列：(表, 列, 类型)
_MIGRATIONS = [
    ("task", "markets", "JSON"),
    ("task", "universes", "JSON"),
    ("task", "symbols_by_market", "JSON"),
    ("result", "market", "VARCHAR DEFAULT ''"),
]


def _migrate(eng) -> None:
    insp = inspect(eng)
    with eng.begin() as conn:
        for table, col, typ in _MIGRATIONS:
            if table in insp.get_table_names() and col not in {c["name"] for c in insp.get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
    # 旧任务：把单市场字段转成多市场字段
    with Session(eng) as s:
        for t in s.exec(select(Task)).all():
            if not t.markets and t.market:
                t.markets = [t.market]
                t.universes = {t.market: t.universe}
                t.symbols_by_market = {t.market: t.symbols or []}
                s.add(t)
        s.commit()


def init_db(url: Optional[str] = None):
    global engine
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url or settings.db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    _migrate(engine)
    return engine


def session() -> Session:
    return Session(engine)
