import pandas as pd
import pytest

from screener.data import kr


@pytest.fixture()
def fake_krx(monkeypatch):
    from pykrx import stock
    from pykrx.website import krx

    monkeypatch.setenv("KRX_ID", "x")
    monkeypatch.setenv("KRX_PW", "y")
    caps = {
        "KOSPI": pd.DataFrame({"시가총액": [5e14, 2e11], "거래대금": [1e12, float("nan")]}, index=["005930", "123450"]),
        "KOSDAQ": pd.DataFrame({"시가총액": [3e12], "거래대금": [5e10]}, index=["247540"]),
    }
    monkeypatch.setattr(stock, "get_nearest_business_day_in_a_week", lambda: "20261117")
    monkeypatch.setattr(stock, "get_market_cap", lambda date, market: caps[market])
    names = {"KOSPI": pd.Series({"005930": "삼성전자", "123450": "하나스팩10호"}),
             "KOSDAQ": pd.DataFrame()}  # pykrx 실패 시 빈 DataFrame 을 돌려준다
    monkeypatch.setattr(krx, "get_market_ticker_and_name", lambda date, market: names[market])
    # 예전 방식으로 호출되면 바로 드러나도록
    monkeypatch.setattr(stock, "get_market_ticker_name", lambda t: pd.DataFrame())
    return stock


def test_universe_names_in_bulk_and_tolerates_failure(fake_krx):
    items = {i.symbol: i for i in kr.KoreaSource().universe("all")}
    assert items["005930.KS"].name == "삼성전자"
    assert items["123450.KS"].is_etf and items["123450.KS"].turnover is None  # 스팩, NaN 거래대금
    assert items["247540.KQ"].name == ""  # 이름 조회 실패 → 빈 이름, 스캔은 계속


def test_index_members_failure_is_explicit(fake_krx, monkeypatch):
    monkeypatch.setattr(fake_krx, "get_index_portfolio_deposit_file", lambda code: pd.DataFrame())
    with pytest.raises(RuntimeError, match="kospi200"):
        kr.KoreaSource().universe("kospi200")
    monkeypatch.setattr(fake_krx, "get_index_portfolio_deposit_file", lambda code: ["005930"])
    assert [i.symbol for i in kr.KoreaSource().universe("kospi200")] == ["005930.KS"]
