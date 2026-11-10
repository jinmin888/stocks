from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, Session, SQLModel, create_engine

from .settings import settings


def now() -> datetime:
    return datetime.now(timezone.utc)


class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    market: str
    timeframe: str = "1d"
    universe: Optional[str] = None
    symbols: List[str] = Field(default_factory=list, sa_column=Column(JSON))
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


engine = None


def init_db(url: Optional[str] = None):
    global engine
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url or settings.db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def session() -> Session:
    return Session(engine)
