from screener import ScreenConfig, Strength, screen
from screener.config import DivergenceConfig, FractalConfig

from .helpers import from_closes


def regular_bottom_df():
    """急跌到低点 → 反弹 → 缓跌到更低的低点（RSI 更高）→ 最后一根阳线确认底分型。"""
    closes = [100 - 1.5 * i for i in range(20)]
    closes += [69, 70.5, 72, 74, 76, 78, 77, 75.5, 74, 72.5, 71.5, 70.8,
               70.3, 69.9, 69.5, 68.4, 71.5]
    df = from_closes(closes)
    df.iloc[-1, df.columns.get_loc("low")] = 69.0
    return df


def hidden_bottom_df():
    """缓跌低点 → 大涨 → 急跌到更高的低点（RSI 更低）。"""
    closes, p = [], 100.0
    for i in range(24):
        p += -2.5 if i % 2 == 0 else 1.8
        closes.append(p)
    closes += [p + 1, p + 3, p + 6, p + 9, p + 12, p + 15, p + 18, p + 15,
               p + 11, p + 7, p + 3, p + 2, p + 4.5]
    df = from_closes(closes)
    df.iloc[-1, df.columns.get_loc("low")] = p + 2.5
    return df


def test_regular_bottom_divergence():
    sigs = screen(regular_bottom_df(), ScreenConfig())
    assert len(sigs) == 1
    s = sigs[0]
    assert s.side == "bottom"
    assert s.fractal.strength == Strength.STRONG
    d = s.divergences[0]
    assert d.kind == "regular"
    assert d.p2 < d.p1 and d.r2 > d.r1
    assert d.r1 < 30
    assert 5 <= d.gap <= 60


def test_oversold_filter_can_block_and_disable():
    df = regular_bottom_df()
    strict = ScreenConfig(divergence=DivergenceConfig(oversold=-1))
    assert screen(df, strict) == []
    off = ScreenConfig(divergence=DivergenceConfig(oversold=None))
    assert screen(df, off)[0].divergences[0].kind == "regular"


def test_gap_limits():
    df = regular_bottom_df()
    assert screen(df, ScreenConfig(divergence=DivergenceConfig(max_gap=5))) == []
    assert screen(df, ScreenConfig(divergence=DivergenceConfig(min_gap=30))) == []


def test_min_fractal_strength_on_second_point():
    df = hidden_bottom_df()  # 第二个底分型为弱
    cfg = DivergenceConfig(hidden=True, min_fractal_strength=Strength.MEDIUM)
    assert screen(df, ScreenConfig(divergence=cfg)) == []


def test_hidden_divergence_is_optional():
    df = hidden_bottom_df()
    assert screen(df, ScreenConfig()) == []  # 隐藏背离默认关闭
    sigs = screen(df, ScreenConfig(divergence=DivergenceConfig(hidden=True)))
    d = sigs[0].divergences[0]
    assert d.kind == "hidden" and d.p2 > d.p1 and d.r2 < d.r1


def test_logic_and_direction():
    df = hidden_bottom_df()
    # 只开分型：最新底分型 → 有信号
    only_fr = ScreenConfig(divergence=DivergenceConfig(enabled=False))
    assert [s.side for s in screen(df, only_fr)] == ["bottom"]
    # AND：背离不满足（隐藏背离关闭）→ 无信号；OR → 有信号
    assert screen(df, ScreenConfig(logic="and")) == []
    assert len(screen(df, ScreenConfig(logic="or"))) == 1
    # 只看顶部
    assert screen(df, ScreenConfig(logic="or", direction="top")) == []
    # 分型强度过滤
    strong_only = ScreenConfig(fractal=FractalConfig(min_strength=Strength.STRONG),
                               divergence=DivergenceConfig(enabled=False))
    assert screen(df, strong_only) == []


def test_min_price_change_pct():
    df = regular_bottom_df()  # 两个低点价格差约 0.9%
    assert screen(df, ScreenConfig(divergence=DivergenceConfig(min_price_change_pct=2.0))) == []
    assert screen(df, ScreenConfig(divergence=DivergenceConfig(min_price_change_pct=None)))


def test_min_rsi_diff_and_score_weights():
    df = regular_bottom_df()  # RSI 差约 21
    assert screen(df, ScreenConfig(divergence=DivergenceConfig(min_rsi_diff=25))) == []
    d = screen(df, ScreenConfig())[0].divergences[0]
    assert abs(d.score - (d.rsi_diff + 0.2 * d.price_change_pct)) < 1e-9


def test_detect_all_includes_history():
    from screener.screen import analyze

    df = regular_bottom_df()
    a = analyze(df, ScreenConfig())
    assert any(d.kind == "regular" and d.side == "bottom" for d in a["divergences"])
    assert len(a["rsi"]) == len(df)
