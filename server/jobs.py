"""扫描执行与定时调度。"""

from __future__ import annotations

import logging
import math
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import select

from screener.config import ScreenConfig
from screener.runner import ScanRequest, run_scan

from . import db
from .settings import settings

log = logging.getLogger("screener.jobs")

_pool: Optional[ThreadPoolExecutor] = None
_market_locks: Dict[str, threading.Lock] = {}
scheduler: Optional[BackgroundScheduler] = None
on_finished = []  # 回调：fn(run, task, results)，用于通知


def _lock(market: str) -> threading.Lock:
    return _market_locks.setdefault(market, threading.Lock())


def _clean(v):
    return None if isinstance(v, float) and math.isnan(v) else v


def enqueue(task_id: int, trigger: str = "manual") -> Optional[int]:
    with db.session() as s:
        task = s.get(db.Task, task_id)
        if task is None:
            return None
        active = s.exec(select(db.Run).where(db.Run.task_id == task_id,
                                             db.Run.status.in_(["queued", "running"]))).first()
        if active:  # 同一个任务不重复排队
            return active.id
        run = db.Run(task_id=task_id, trigger=trigger, snapshot=task.model_dump(mode="json"))
        s.add(run)
        s.commit()
        s.refresh(run)
        run_id = run.id
    _pool.submit(_execute, run_id)
    return run_id


def _execute(run_id: int) -> None:
    with db.session() as s:
        run = s.get(db.Run, run_id)
        snap = run.snapshot
    req = ScanRequest(market=snap["market"], timeframe=snap["timeframe"], universe=snap["universe"],
                      symbols=snap["symbols"] or [], exchange=snap["exchange"])
    with _lock(req.market):  # 同一市场串行，避免缓存写冲突和限流
        _update(run_id, status="running", started_at=db.now(), message="")
        try:
            cfg = ScreenConfig.model_validate(snap["config"] or {})

            def progress(done, total, msg):
                fields = {"done": done, "total": total}
                if msg:
                    fields["message"] = msg[:500]
                _update(run_id, **fields)

            out = run_scan(req, cfg, settings.cache_dir, settings.retry_wait, progress)
            with db.session() as s:
                for r in out.rows:
                    s.add(db.Result(run_id=run_id, **{k: _clean(v) for k, v in r.items()}))
                s.commit()
            _update(run_id, status="done", finished_at=db.now(), total=out.total, done=out.total,
                    failed=out.failed, message="")
        except Exception as e:
            log.exception("run %s failed", run_id)
            _update(run_id, status="failed", finished_at=db.now(), error=f"{type(e).__name__}: {e}")
    _notify(run_id)


def _update(run_id: int, **fields) -> None:
    with db.session() as s:
        run = s.get(db.Run, run_id)
        for k, v in fields.items():
            setattr(run, k, v)
        s.add(run)
        s.commit()


def _notify(run_id: int) -> None:
    with db.session() as s:
        run = s.get(db.Run, run_id)
        task = s.get(db.Task, run.task_id) if run.task_id else None
        results = s.exec(select(db.Result).where(db.Result.run_id == run_id)).all()
    for cb in on_finished:
        try:
            cb(run, task, results)
        except Exception:
            log.exception("notify callback failed for run %s", run_id)


def sync_task(task: db.Task) -> None:
    """任务新建 / 修改 / 删除后同步定时器。"""
    if scheduler is None:
        return
    job_id = f"task-{task.id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    if task.enabled and task.cron:
        scheduler.add_job(enqueue, CronTrigger.from_crontab(task.cron, timezone=task.timezone),
                          id=job_id, args=[task.id, "schedule"], misfire_grace_time=600,
                          coalesce=True)


def remove_task(task_id: int) -> None:
    if scheduler and scheduler.get_job(f"task-{task_id}"):
        scheduler.remove_job(f"task-{task_id}")


def next_run(task_id: int):
    job = scheduler.get_job(f"task-{task_id}") if scheduler else None
    return job.next_run_time if job else None


def start() -> None:
    global _pool, scheduler
    _pool = ThreadPoolExecutor(max_workers=settings.max_workers)
    # 服务重启时，上次未完成的运行标记为失败
    with db.session() as s:
        for run in s.exec(select(db.Run).where(db.Run.status.in_(["queued", "running"]))).all():
            run.status, run.error, run.finished_at = "failed", "服务重启，运行中断", db.now()
            s.add(run)
        s.commit()
        tasks = s.exec(select(db.Task)).all()
    if settings.enable_scheduler:
        scheduler = BackgroundScheduler()
        scheduler.start()
        for t in tasks:
            sync_task(t)


def stop() -> None:
    if scheduler:
        scheduler.shutdown(wait=False)
    if _pool:
        _pool.shutdown(wait=False, cancel_futures=True)
