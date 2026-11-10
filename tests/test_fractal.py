import pytest

from screener.config import FractalConfig, Strength
from screener.fractal import detect, filter_bi, find_fractals, latest_signal, merge_bars

from .helpers import bars

K1 = (10.0, 10.0, 8.0, 8.5)  # 阴线，实体中点 9.25
K2 = (8.5, 9.0, 7.0, 8.0)


def test_inclusion_up_takes_high_high():
    df = bars([(5, 10, 5, 9), (9, 12, 7, 11), (11, 11, 8, 10)])
    m = merge_bars(df)
    assert len(m) == 2
    assert (m[1].high, m[1].low) == (12, 8)
    assert m[1].close == 10  # 组内最后一根原始收盘价
    assert m[1].open == 9  # 组内第一根原始开盘价
    assert (m[1].start, m[1].end) == (1, 2)


def test_inclusion_down_takes_low_low():
    df = bars([(12, 12, 8, 9), (9, 10, 6, 7), (7, 9, 7, 8)])
    m = merge_bars(df)
    assert len(m) == 2
    assert (m[1].high, m[1].low) == (9, 6)


def test_inclusion_off_keeps_all_bars():
    df = bars([(5, 10, 5, 9), (9, 12, 7, 11), (11, 11, 8, 10)])
    assert len(merge_bars(df, inclusion=False)) == 3


@pytest.mark.parametrize("k3, expected", [
    ((8.0, 11.0, 7.5, 10.5), Strength.STRONG),   # 阳线且收盘 > K1 高点
    ((11.0, 11.2, 7.5, 10.5), Strength.MEDIUM),  # 收盘 > K1 高点但为阴线
    ((8.0, 9.8, 7.5, 9.5), Strength.MEDIUM),     # 收盘 > K1 实体中点
    ((8.0, 9.5, 7.5, 9.1), Strength.WEAK),       # 仅满足结构
])
def test_bottom_fractal_strength(k3, expected):
    f = find_fractals(merge_bars(bars([K1, K2, k3])), FractalConfig())
    assert len(f) == 1 and f[0].type == "bottom"
    assert f[0].price == 7.0
    assert f[0].strength == expected


def test_top_fractal_strength_symmetric():
    k1 = (8.0, 10.0, 8.0, 9.5)
    k2 = (9.5, 11.0, 9.0, 10.0)
    k3 = (10.0, 10.5, 7.0, 7.5)  # 阴线且收盘 < K1 低点
    f = find_fractals(merge_bars(bars([k1, k2, k3])), FractalConfig())
    assert f[0].type == "top" and f[0].strength == Strength.STRONG


def test_volume_check_downgrades_strong():
    rows = [K1, K2, (8.0, 11.0, 7.5, 10.5)]
    cfg = FractalConfig(volume_check=True, volume_ma=2)
    low_vol = find_fractals(merge_bars(bars(rows, [100, 100, 90])), cfg)
    assert low_vol[0].strength == Strength.MEDIUM
    high_vol = find_fractals(merge_bars(bars(rows, [100, 100, 150])), cfg)
    assert high_vol[0].strength == Strength.STRONG


def _seq(highs_lows):
    return bars([(l, h, l, (h + l) / 2) for h, l in highs_lows])


def test_strict_bi_skips_close_opposite_fractal():
    # 顶(k2=1) 与 底(k2=3) 只差 2 根，严格模式下底被忽略
    df = _seq([(10, 8), (12, 10), (11, 9), (9, 7), (10, 8)])
    raw = find_fractals(merge_bars(df), FractalConfig())
    assert [f.type for f in raw] == ["top", "bottom"]
    assert [f.type for f in filter_bi(raw)] == ["top"]


def test_strict_bi_keeps_distant_fractals():
    df = _seq([(10, 8), (12, 10), (11, 9), (10, 8), (9, 7), (8, 6), (9, 7),
               (10, 8), (11, 9), (10, 8), (13, 11), (12, 10)])
    f = detect(df, FractalConfig())
    assert [x.type for x in f] == ["top", "bottom", "top"]
    assert f[-1].price == 13


def test_latest_signal_recency_and_k4():
    df = bars([K1, K2, (8.0, 11.0, 7.5, 10.5)])
    fr = detect(df, FractalConfig())
    assert latest_signal(fr, len(df), FractalConfig()) is not None
    # 开启 K4 确认：还没有 K4 → 无信号
    assert latest_signal(fr, len(df), FractalConfig(confirm_k4=True)) is None
    # 强度过滤
    assert latest_signal(fr, len(df), FractalConfig(min_strength=Strength.STRONG)) is not None

    df4 = bars([K1, K2, (8.0, 11.0, 7.5, 10.5), (10.5, 12.0, 9.0, 11.5)])
    fr4 = detect(df4, FractalConfig())
    # 不开确认：K3 不是最新一根 → 无信号
    assert latest_signal(fr4, len(df4), FractalConfig()) is None
    # 开确认：K4 未破 K2 低点且为最新一根 → 有信号
    assert latest_signal(fr4, len(df4), FractalConfig(confirm_k4=True)) is not None


def test_strict_bi_replaces_same_type_with_more_extreme():
    # 顶(12) → 底(6) → 中间的顶(11)距离不足被忽略 → 更低的底(5)替换底(6)
    df = _seq([(10, 8), (12, 10), (11, 9), (10, 8), (9, 7), (8, 6), (9, 7),
               (11, 9), (8, 6), (7, 5), (8, 6)])
    f = detect(df, FractalConfig())
    assert [x.type for x in f] == ["top", "bottom"]
    assert f[-1].price == 5
