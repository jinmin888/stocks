# stocks

多市场（加密货币、韩国股市、A 股、美股、港股）筛选器：顶底分型（强/中/弱）与 RSI 背离。

需求规格见 [docs/spec.md](docs/spec.md)。

## 当前进度

- [x] 筛选核心：包含处理、分型识别与强弱分级、严格笔过滤、RSI、常规/隐藏背离、组合逻辑
- [x] 数据源：加密货币（ccxt）、A 股（akshare）、美股/港股（yfinance），本地 Parquet 缓存，命令行扫描
- [ ] 指数成分股列表、韩国股市列表与市值
- [ ] FastAPI 后端 + 定时扫描
- [ ] React 前端（中文 / 韩文）
- [ ] Docker 部署
- [ ] 回测

## 开发

```bash
pip install -e ".[dev]"
pytest
```

## 命令行扫描

```bash
python -m screener.cli --market crypto --timeframe 4h --universe top100
python -m screener.cli --market us --symbols AAPL MSFT NVDA --config config.yaml --csv out.csv
```
