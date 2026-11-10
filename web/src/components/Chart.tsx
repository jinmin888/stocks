import { useEffect, useRef, useState } from "react";
import {
  CandlestickSeries, ColorType, CrosshairMode, HistogramSeries, LineSeries, LineStyle,
  createChart, createSeriesMarkers, type IChartApi, type SeriesMarker, type Time, type UTCTimestamp,
} from "lightweight-charts";
import { api, type ChartData } from "../api";
import { useI18n } from "../i18n";

const KST_OFFSET = 9 * 3600; // 加密货币按韩国时间显示（KST 无夏令时）

function cssVar(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export default function Chart({ market, symbol, timeframe, runId, title, onClose }: {
  market: string; symbol: string; timeframe: string; runId?: number; title: string; onClose?: () => void;
}) {
  const { t, lang } = useI18n();
  const box = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<ChartData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    setError("");
    api.chart({ market, symbol, timeframe, run_id: runId }).then(setData).catch((e) => setError(e.message));
  }, [market, symbol, timeframe, runId]);

  useEffect(() => {
    if (!data || !box.current) return;
    const shift = market === "crypto" ? KST_OFFSET : 0;
    const T = (s: number) => (s + shift) as UTCTimestamp;
    const up = cssVar("--bull"), down = cssVar("--bear");
    const text = cssVar("--muted"), grid = cssVar("--border");
    const intraday = ["15m", "1h", "4h"].includes(timeframe);

    const chart: IChartApi = createChart(box.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: text,
        panes: { separatorColor: grid } },
      grid: { vertLines: { color: grid }, horzLines: { color: grid } },
      crosshair: { mode: CrosshairMode.Normal },
      timeScale: { timeVisible: intraday, secondsVisible: false, borderColor: grid },
      rightPriceScale: { borderColor: grid },
      localization: { locale: lang === "ko" ? "ko-KR" : "zh-CN", dateFormat: "yyyy-MM-dd" },
    });

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: up, downColor: down, borderUpColor: up, borderDownColor: down, wickUpColor: up, wickDownColor: down,
    });
    candles.setData(data.bars.map((b) => ({ time: T(b.time), open: b.open, high: b.high, low: b.low, close: b.close })));

    const vol = chart.addSeries(HistogramSeries, { priceScaleId: "vol", priceFormat: { type: "volume" },
      lastValueVisible: false, priceLineVisible: false });
    vol.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    vol.setData(data.bars.map((b) => ({ time: T(b.time), value: b.volume,
      color: (b.close >= b.open ? up : down) + "55" })));

    // 分型标记：强 / 中 / 弱 透明度递减
    const alpha: Record<string, string> = { strong: "ff", medium: "bb", weak: "77" };
    const label: Record<string, string> = { strong: t("strong"), medium: t("medium"), weak: t("weak") };
    const markers: SeriesMarker<Time>[] = data.fractals.map((f) => ({
      time: T(f.time),
      position: f.type === "top" ? "aboveBar" : "belowBar",
      shape: f.type === "top" ? "arrowDown" : "arrowUp",
      color: (f.type === "top" ? down : up) + alpha[f.strength],
      text: label[f.strength],
    }));
    createSeriesMarkers(candles, markers.sort((a, b) => (a.time as number) - (b.time as number)));

    // RSI 副图
    const rsi = chart.addSeries(LineSeries, { color: cssVar("--accent"), lineWidth: 1,
      priceLineVisible: false, lastValueVisible: true }, 1);
    rsi.setData(data.rsi.map((p) => ({ time: T(p.time), value: p.value })));
    for (const lvl of [data.config.oversold, data.config.overbought]) {
      if (lvl !== null) rsi.createPriceLine({ price: lvl, color: grid, lineStyle: LineStyle.Dashed,
        lineWidth: 1, axisLabelVisible: false, title: "" });
    }
    chart.panes()[1]?.setHeight(140);

    // 背离连线：价格图和 RSI 图各画一条虚线
    for (const d of data.divergences) {
      const color = (d.side === "bottom" ? up : down) + (d.kind === "regular" ? "" : "99");
      const opts = { color, lineWidth: 2 as const, lineStyle: LineStyle.Dashed, priceLineVisible: false,
        lastValueVisible: false, crosshairMarkerVisible: false, pointMarkersVisible: false };
      chart.addSeries(LineSeries, opts, 0).setData([
        { time: T(d.from.time), value: d.from.price }, { time: T(d.to.time), value: d.to.price }]);
      if (d.from.rsi !== undefined && d.to.rsi !== undefined) {
        chart.addSeries(LineSeries, opts, 1).setData([
          { time: T(d.from.time), value: d.from.rsi }, { time: T(d.to.time), value: d.to.rsi }]);
      }
    }

    const n = data.bars.length;
    chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, n - 150), to: n + 3 });
    return () => chart.remove();
  }, [data, market, timeframe, lang, t]);

  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="row">
        <strong>{title}</strong>
        <span className="badge">{timeframe}</span>
        <span className="spacer" />
        {onClose && <button className="link" onClick={onClose} aria-label="close">✕</button>}
      </div>
      {error ? <div className="error">{error}</div> : !data ? <div className="muted">{t("loading")}</div> : null}
      <div ref={box} className="chart-box" style={{ display: data ? "block" : "none" }} />
      <div className="muted small">{t("legendFractal")} · {t("legendDiv")}</div>
    </div>
  );
}
