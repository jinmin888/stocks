import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type Market, type SignalDate, type SignalRow } from "../api";
import Chart from "../components/Chart";
import { fmtNum } from "../format";
import { MARKET_NAMES, useI18n, type Key } from "../i18n";

const STRENGTH: Record<string, number> = { strong: 3, medium: 2, weak: 1 };

function toCsv(rows: SignalRow[]): string {
  const cols: (keyof SignalRow)[] = ["date", "market", "timeframe", "symbol", "name", "side", "fractal_strength",
    "divergence", "divergence_score", "rsi_diff", "price_change_pct", "rsi", "close", "tasks"];
  const esc = (v: unknown) => {
    const s = Array.isArray(v) ? v.join(" / ") : v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
}

export default function Signals() {
  const { t, lang } = useI18n();
  const [params, setParams] = useSearchParams();
  const [dates, setDates] = useState<SignalDate[] | null>(null);
  const [rows, setRows] = useState<SignalRow[] | null>(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<SignalRow | null>(null);
  const [market, setMarket] = useState<"" | Market>("");
  const [side, setSide] = useState<"" | "bottom" | "top">("");
  const [timeframe, setTimeframe] = useState("");
  const [minStrength, setMinStrength] = useState(0);
  const [divOnly, setDivOnly] = useState(false);
  const [query, setQuery] = useState("");

  const date = params.get("date") ?? dates?.[0]?.date ?? "";

  useEffect(() => {
    api.signalDates().then(setDates).catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!date) return;
    setRows(null);
    setSelected(null);
    api.signals(date).then(setRows).catch((e) => setError(e.message));
  }, [date]);

  const filtered = useMemo(() => (rows ?? []).filter((r) => {
    if (market && r.market !== market) return false;
    if (side && r.side !== side) return false;
    if (timeframe && r.timeframe !== timeframe) return false;
    if (minStrength && (STRENGTH[r.fractal_strength ?? ""] ?? 0) < minStrength) return false;
    if (divOnly && !r.divergence) return false;
    const q = query.trim().toLowerCase();
    return !q || r.symbol.toLowerCase().includes(q) || r.name.toLowerCase().includes(q);
  }), [rows, market, side, timeframe, minStrength, divOnly, query]);

  const markets = useMemo(() => [...new Set((rows ?? []).map((r) => r.market))], [rows]);
  const timeframes = useMemo(() => [...new Set((rows ?? []).map((r) => r.timeframe))], [rows]);

  const go = (d: string) => setParams({ date: d });
  const idx = dates?.findIndex((d) => d.date === date) ?? -1;
  const older = dates && idx >= 0 ? dates[idx + 1]?.date : undefined;
  const newer = dates && idx > 0 ? dates[idx - 1]?.date : undefined;

  const download = () => {
    const blob = new Blob(["﻿" + toCsv(filtered)], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `signals-${date}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  if (error) return <div className="error">{error}</div>;
  if (dates === null) return <div className="muted">{t("loading")}</div>;
  if (dates.length === 0) return (
    <div className="stack"><h1>{t("signalsByDate")}</h1><div className="panel muted">{t("noSignals")}</div></div>
  );

  return (
    <div className="stack">
      <div className="row">
        <h1 style={{ margin: 0 }}>{t("signalsByDate")}</h1>
        <span className="spacer" />
        <button disabled={!older} onClick={() => older && go(older)}>◀ {t("prevDay")}</button>
        <input type="date" value={date} onChange={(e) => e.target.value && go(e.target.value)} />
        <button disabled={!newer} onClick={() => newer && go(newer)}>{t("nextDay")} ▶</button>
      </div>
      <div className="muted small">{t("signalDateHint")}</div>

      <div className="signals-layout">
        <div className="panel date-list">
          <div className="muted small" style={{ marginBottom: 6 }}>{t("signalDates")}</div>
          {dates.map((d) => (
            <button key={d.date} className={`date-item${d.date === date ? " active" : ""}`} onClick={() => go(d.date)}>
              <span>{d.date}</span>
              <span className="small">
                {d.bottom > 0 && <span className="bull">▲{d.bottom}</span>}{" "}
                {d.top > 0 && <span className="bear">▼{d.top}</span>}
              </span>
            </button>
          ))}
        </div>

        <div className="stack" style={{ minWidth: 0 }}>
          <div className="panel row">
            <select value={market} onChange={(e) => setMarket(e.target.value as "" | Market)}>
              <option value="">{t("allMarkets")}</option>
              {markets.map((m) => <option key={m} value={m}>{MARKET_NAMES[m]?.[lang] ?? m}</option>)}
            </select>
            <select value={side} onChange={(e) => setSide(e.target.value as "" | "bottom" | "top")}>
              <option value="">{t("allSides")}</option>
              <option value="bottom">{t("bottom")}</option>
              <option value="top">{t("top")}</option>
            </select>
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
              <option value="">{t("allTimeframes")}</option>
              {timeframes.map((tf) => <option key={tf}>{tf}</option>)}
            </select>
            <select value={minStrength} onChange={(e) => setMinStrength(Number(e.target.value))}>
              <option value={0}>{t("strength")}: {t("any")}</option>
              <option value={2}>{t("strength")}: {t("medium")}+</option>
              <option value={3}>{t("strength")}: {t("strong")}</option>
            </select>
            <label className="check">
              <input type="checkbox" checked={divOnly} onChange={(e) => setDivOnly(e.target.checked)} />{t("divOnly")}
            </label>
            <input placeholder={t("search")} value={query} onChange={(e) => setQuery(e.target.value)} style={{ width: 160 }} />
            <span className="spacer" />
            <span className="muted small">{t("shown")} {filtered.length} / {rows?.length ?? 0}</span>
            {filtered.length > 0 && <button onClick={download}>{t("downloadCsv")}</button>}
          </div>

          <div className={`split${selected ? " with-chart" : ""}`}>
            <div className="panel table-wrap">
              {rows === null ? <div className="muted">{t("loading")}</div>
                : filtered.length === 0 ? <div className="muted">{t("noSignalsOnDate")}</div> : (
                  <table>
                    <thead>
                      <tr>
                        <th>{t("market")}</th><th>{t("symbol")}</th><th>{t("timeframe")}</th><th>{t("side")}</th>
                        <th>{t("strength")}</th><th>{t("divType")}</th><th className="num">{t("score")}</th>
                        <th className="num">RSI</th><th className="num">{t("close")}</th><th>{t("sourceTasks")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((r) => (
                        <tr key={`${r.market}-${r.symbol}-${r.side}-${r.timeframe}`}
                          className={`clickable${selected === r ? " selected" : ""}`} onClick={() => setSelected(r)}>
                          <td><span className="badge">{MARKET_NAMES[r.market]?.[lang] ?? r.market}</span></td>
                          <td><strong>{r.symbol}</strong> <span className="muted small">{r.name}</span></td>
                          <td>{r.timeframe}</td>
                          <td><span className={`badge ${r.side === "bottom" ? "bull" : "bear"}`}>
                            {r.side === "bottom" ? "▲" : "▼"} {t(r.side)}</span></td>
                          <td>{r.fractal_strength
                            ? <span className={`badge s-${r.fractal_strength}`}>{t(r.fractal_strength as Key)}</span> : "—"}</td>
                          <td>{r.divergence ? t(`${r.divergence}Short` as Key) : "—"}</td>
                          <td className="num">{fmtNum(r.divergence_score)}</td>
                          <td className="num">{fmtNum(r.rsi)}</td>
                          <td className="num">{fmtNum(r.close)}</td>
                          <td className="small">
                            <Link to={`/runs/${r.run_id}`} onClick={(e) => e.stopPropagation()}>{r.tasks.join(", ")}</Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
            </div>
            {selected && (
              <div className="panel">
                <Chart market={selected.market} symbol={selected.symbol} timeframe={selected.timeframe}
                  runId={selected.run_id} title={`${selected.symbol} ${selected.name}`} onClose={() => setSelected(null)} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
