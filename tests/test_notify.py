from server import db, notify
from server.settings import settings


def _run(**kw):
    return db.Run(id=7, status=kw.get("status", "done"), trigger=kw.get("trigger", "manual"),
                  error=kw.get("error"),
                  snapshot={"name": "A股日线", "market": "cn", "timeframe": "1d"})


def _res(i, side="bottom", score=10.0):
    return db.Result(run_id=7, symbol=f"60{i:04d}", side=side, date="2026-11-10", close=1.0,
                     fractal_strength="strong", divergence="regular", divergence_score=score)


def test_summary_fits_limit_and_ranks_by_score():
    results = [_res(i, score=i) for i in range(40)] + [_res(100 + i, "top") for i in range(5)]
    for lang in ("zh", "ko"):
        text = notify.format_summary(_run(), results, lang)
        assert len(text) <= notify.TEXT_LIMIT
        lines = text.splitlines()
        assert lines[0].startswith("[A股日线]")
        assert "40" in lines[1] and "5" in lines[1]
        assert lines[2].startswith("▲ 600039")  # 分数最高的在前
        assert lines[2].endswith("+35")  # 每个方向最多 5 只，其余显示数量
        assert lines[3].startswith("▼ 600100")  # 看跌也有位置


def test_notify_rules(monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "send_text", lambda text, link, button: sent.append((text, link)))
    monkeypatch.setattr(settings, "kakao_rest_key", "k")
    monkeypatch.setattr(settings, "public_url", "https://x.example")
    task = db.Task(id=1, name="A股日线", market="cn", notify=True)

    notify.on_run_finished(_run(), task, [])  # 无结果不发
    assert sent == []
    notify.on_run_finished(_run(), task.model_copy(update={"notify": False}), [_res(1)])  # 任务关闭通知
    assert sent == []
    notify.on_run_finished(_run(), task, [_res(1)])
    assert sent[-1][1] == "https://x.example/runs/7"
    notify.on_run_finished(_run(status="failed", trigger="manual", error="boom"), task, [])
    assert len(sent) == 1  # 手动运行失败不发
    notify.on_run_finished(_run(status="failed", trigger="schedule", error="boom"), task, [])
    assert "boom" in sent[-1][0]


def test_summary_multi_market_title():
    run = db.Run(id=8, status="done", snapshot={"name": "全部", "markets": ["kr", "us"], "timeframe": "1d"})
    r1 = db.Result(run_id=8, market="kr", symbol="005930.KS", name="삼성전자", side="bottom", date="d", close=1)
    r2 = db.Result(run_id=8, market="us", symbol="AAPL", name="Apple Inc.", side="bottom", date="d", close=1)
    text = notify.format_summary(run, [r1, r2], "ko")
    assert text.splitlines()[0] == "[全部] 한국 주식+미국 주식 1d"
    assert "삼성전자" in text and "AAPL" in text and "Apple" not in text
