"""KakaoTalk「나에게 보내기」通知。

流程：网页上点「连接 KakaoTalk」→ /api/kakao/login 跳转到 Kakao 授权 → 回调 /api/kakao/callback
保存令牌 → 扫描完成后调用 send_run_summary。access token 约 6 小时过期，refresh token 约 2 个月；
每次发送前按需刷新，刷新时 Kakao 会在 refresh token 剩余不足 1 个月时发放新的。
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from . import db, jobs
from .settings import settings

log = logging.getLogger("screener.notify")
AUTH = "https://kauth.kakao.com"
API = "https://kapi.kakao.com"
TEXT_LIMIT = 200  # Kakao 文本模板上限

MARKET = {
    "zh": {"crypto": "加密货币", "kr": "韩国股市", "cn": "A股", "us": "美股", "hk": "港股"},
    "ko": {"crypto": "암호화폐", "kr": "한국 주식", "cn": "중국 A주", "us": "미국 주식", "hk": "홍콩 주식"},
}
TXT = {
    "zh": {"bull": "看涨", "bear": "看跌", "view": "查看结果", "failed": "扫描失败",
           "strong": "强", "medium": "中", "weak": "弱", "regular_short": "背离", "hidden_short": "隐背",
           "test": "测试消息：KakaoTalk 通知已连接。"},
    "ko": {"bull": "상승", "bear": "하락", "view": "결과 보기", "failed": "스캔 실패",
           "strong": "강", "medium": "중", "weak": "약", "regular_short": "다이버", "hidden_short": "히든",
           "test": "테스트 메시지: 카카오톡 알림이 연결되었습니다."},
}

router = APIRouter(prefix="/api/kakao")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(d: Optional[datetime]) -> Optional[datetime]:
    return d.replace(tzinfo=timezone.utc) if d is not None and d.tzinfo is None else d


def _require_user(request: Request) -> str:
    from .main import require_user
    return require_user(request)


def _token_request(data: dict) -> dict:
    data = {**data, "client_id": settings.kakao_rest_key}
    if settings.kakao_client_secret:
        data["client_secret"] = settings.kakao_client_secret
    r = requests.post(f"{AUTH}/oauth/token", data=data, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"Kakao token error {r.status_code}: {r.text[:300]}")
    return r.json()


def _save(tok: dict) -> None:
    with db.session() as s:
        row = s.get(db.KakaoToken, 1)
        access_exp = _now() + timedelta(seconds=int(tok.get("expires_in", 21599)) - 60)
        if row is None:
            row = db.KakaoToken(access_token=tok["access_token"], access_expires_at=access_exp,
                                refresh_token=tok["refresh_token"])
        row.access_token, row.access_expires_at = tok["access_token"], access_exp
        if tok.get("refresh_token"):  # 刷新时只有快过期才会返回新的 refresh token
            row.refresh_token = tok["refresh_token"]
            row.refresh_expires_at = _now() + timedelta(seconds=int(tok.get("refresh_token_expires_in", 0)))
        row.updated_at = _now()
        s.add(row)
        s.commit()


def access_token() -> Optional[str]:
    with db.session() as s:
        row = s.get(db.KakaoToken, 1)
        if row is None:
            return None
        if _aware(row.access_expires_at) > _now():
            return row.access_token
        refresh = row.refresh_token
    _save(_token_request({"grant_type": "refresh_token", "refresh_token": refresh}))
    with db.session() as s:
        return s.get(db.KakaoToken, 1).access_token


def send_text(text: str, link: str, button: str) -> None:
    token = access_token()
    if token is None:
        raise RuntimeError("KakaoTalk 未连接")
    template = {"object_type": "text", "text": text[:TEXT_LIMIT],
                "link": {"web_url": link, "mobile_web_url": link}, "button_title": button}
    r = requests.post(f"{API}/v2/api/talk/memo/default/send",
                      headers={"Authorization": f"Bearer {token}"},
                      data={"template_object": json.dumps(template, ensure_ascii=False)}, timeout=15)
    if r.status_code != 200:
        code = None
        try:
            code = r.json().get("code")
        except ValueError:
            pass
        if code == -402:  # 用户授权时没有勾选「카카오톡 메시지 전송」
            raise RuntimeError("카카오톡 메시지 전송 동의가 없습니다 / 未同意发送消息：请在设置页「重新连接」，"
                               "并在同意画面勾选「카카오톡 메시지 전송」")
        raise RuntimeError(f"Kakao send error {r.status_code}: {r.text[:300]}")


PER_SIDE = 5  # 每个方向最多列出几只


def format_summary(run: db.Run, results: List[db.Result], lang: str) -> str:
    """生成不超过 200 字的摘要：标题、看涨/看跌数量、各方向按强度分排序的前几只。"""
    tx, snap = TXT[lang], run.snapshot or {}
    markets = [m for m, _, _ in db.task_markets(snap)]
    names = "+".join(MARKET[lang].get(m, m) for m in markets)
    title = f"[{snap.get('name', '')}] {names} {snap.get('timeframe', '')}"
    bull = [r for r in results if r.side == "bottom"]
    bear = [r for r in results if r.side == "top"]
    head = [title, f"{tx['bull']} {len(bull)} · {tx['bear']} {len(bear)}"]

    def label(r: db.Result) -> str:
        # A 股、韩国股市显示名称；其他市场名称太长或与代码相同，显示代码
        market = r.market or (markets[0] if markets else "")
        shown = r.name if market in ("cn", "kr") and r.name else r.symbol.removesuffix("/USDT")
        tags = [tx[r.fractal_strength]] if r.fractal_strength else []
        if r.divergence:
            tags.append(tx[f"{r.divergence}_short"])
        return f"{shown}({'·'.join(tags)})" if tags else shown

    def rank(r: db.Result):
        return (r.divergence_score or 0, {"strong": 3, "medium": 2, "weak": 1}.get(r.fractal_strength or "", 0))

    groups = [(a, sorted(g, key=rank, reverse=True)) for a, g in (("▲", bull), ("▼", bear)) if g]
    budget = (TEXT_LIMIT - len("\n".join(head)) - 1) // max(1, len(groups)) - 1
    lines = list(head)
    for arrow, ranked in groups:
        line = arrow
        for i, r in enumerate(ranked):
            rest = len(ranked) - i
            candidate = f"{line} {label(r)}"
            if i >= PER_SIDE or len(candidate) + len(f" +{rest}") > budget:
                line += f" +{rest}"
                break
            line = candidate
        lines.append(line)
    return "\n".join(lines)[:TEXT_LIMIT]


def on_run_finished(run: db.Run, task: Optional[db.Task], results: List[db.Result]) -> None:
    """扫描结束回调：任务开启通知，且有结果（或定时任务失败）时发送。"""
    if task is None or not task.notify or not settings.kakao_rest_key:
        return
    lang = settings.notify_lang if settings.notify_lang in TXT else "zh"
    link = f"{settings.public_url}/runs/{run.id}"
    if run.status == "done" and results:
        text = format_summary(run, results, lang)
    elif run.status == "failed" and run.trigger == "schedule":
        text = f"[{task.name}] {TXT[lang]['failed']}\n{(run.error or '')[:150]}"
    else:
        return
    try:
        send_text(text, link, TXT[lang]["view"])
    except Exception:
        log.exception("KakaoTalk 发送失败 (run %s)", run.id)


jobs.on_finished.append(on_run_finished)


# ---------------------------------------------------------------- 路由

@router.get("/status")
def status(_: str = Depends(_require_user)):
    with db.session() as s:
        row = s.get(db.KakaoToken, 1)
    return {
        "configured": bool(settings.kakao_rest_key),
        "connected": row is not None,
        "refresh_expires_at": _aware(row.refresh_expires_at).isoformat() if row and row.refresh_expires_at else None,
        "redirect_uri": settings.kakao_redirect_uri,
        "lang": settings.notify_lang,
    }


@router.get("/login")
def login(request: Request, _: str = Depends(_require_user)):
    if not settings.kakao_rest_key:
        raise HTTPException(400, "未设置 KAKAO_REST_API_KEY")
    state = secrets.token_urlsafe(16)
    request.session["kakao_state"] = state
    q = urlencode({"client_id": settings.kakao_rest_key, "redirect_uri": settings.kakao_redirect_uri,
                   "response_type": "code", "scope": "talk_message", "state": state})
    return RedirectResponse(f"{AUTH}/oauth/authorize?{q}")


@router.get("/callback")
def callback(request: Request, code: str = "", state: str = "", error: str = ""):
    _require_user(request)
    if error or not code:
        return RedirectResponse(f"/settings?kakao=error&reason={error or 'no_code'}")
    if state != request.session.pop("kakao_state", None):
        raise HTTPException(400, "state 不匹配")
    try:
        _save(_token_request({"grant_type": "authorization_code", "code": code,
                              "redirect_uri": settings.kakao_redirect_uri}))
    except Exception as e:
        log.exception("Kakao token exchange failed")
        return RedirectResponse(f"/settings?kakao=error&reason={type(e).__name__}")
    return RedirectResponse("/settings?kakao=connected")


@router.post("/test")
def test(_: str = Depends(_require_user)):
    lang = settings.notify_lang if settings.notify_lang in TXT else "zh"
    try:
        send_text(TXT[lang]["test"], settings.public_url, TXT[lang]["view"])
    except Exception as e:
        raise HTTPException(502, str(e))
    return {"ok": True}


@router.delete("")
def disconnect(_: str = Depends(_require_user)):
    with db.session() as s:
        row = s.get(db.KakaoToken, 1)
        if row:
            s.delete(row)
            s.commit()
    return {"ok": True}
