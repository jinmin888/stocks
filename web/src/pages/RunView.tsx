import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type ResultRow, type RunDetail } from "../api";
import Chart from "../components/Chart";
import RunStatus from "../components/RunStatus";
import { fmtNum, fmtTime } from "../format";
import { MARKET_NAMES, useI18n, type Key } from "../i18n";

type SortKey = keyof ResultRow;
const STRENGTH_ORDER: Record<string, number> = { strong: 3, medium: 2, weak: 1 };

function toCsv(rows: ResultRow[]): string {
  const cols: SortKey[] = ["market", "symbol", "name", "side", "date", "close", "rsi", "fractal_strength",
    "divergence", "divergence_score", "price_change_pct", "rsi_diff"];
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
}

export default function RunView() {
  const { t, lang } = useI18n();
  const { id } = useParams();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "divergence_score", desc: true });
  const [selected, setSelected] = useState<ResultRow | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const load = () => api.run(Number(id)).then((r) => {
      setRun(r);
      if (r.status === "queued" || r.status === "running") timer = setTimeout(load, 2000);
    }).catch((e) => setError(e.message));
    load();
    return () => clearTimeout(timer);
  }, [id]);

  const rows = useMemo(() => {
    if (!run) return [];
    const val = (r: ResultRow) => {
      const v = r[sort.key];
      if (sort.key === "fractal_strength") return STRENGTH_ORDER[v as string] ?? 0;
      return v ?? -Infinity;
    };
    return [...run.results].sort((a, b) => {
      const x = val(a), y = val(b);
      const c = x < y ? -1 : x > y ? 1 : 0;
      return sort.desc ? -c : c;
    });
  }, [run, sort]);

  if (!run) return <div className={error ? "error" : "muted"}>{error || t("loading")}</div>;

  const header = (key: SortKey, label: string, num = false) => (
    <th className={`sortable${num ? " num" : ""}`}
      onClick={() => setSort({ key, desc: sort.key === key ? !sort.desc : true })}>
      {label}{sort.key === key ? (sort.desc ? " ↓" : " ↑") : ""}
    </th>
  );
  const download = () => {
    const blob = new Blob(["﻿" + toCsv(rows)], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${run.task_name ?? "scan"}-${run.id}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  const pct = run.total ? Math.round((run.done / run.total) * 100) : 0;
  const multi = run.markets.length > 1;

  return (
    <div className="stack">
      <div className="row">
        <h1 style={{ margin: 0 }}>{run.task_name}</h1>
        {run.markets.map((m) => <span className="badge" key={m}>{MARKET_NAMES[m]?.[lang] ?? m}</span>)}
        <span className="badge">{run.timeframe}</span>
        <RunStatus run={run} />
        <span className="spacer" />
        {run.task_id && <Link to={`/tasks/${run.task_id}`}><button>{t("editTask")}</button></Link>}
        {rows.length > 0 && <button onClick={download}>{t("downloadCsv")}</button>}
      </div>
      <div className="muted small">
        {fmtTime(run.started_at ?? run.created_at, lang)} → {fmtTime(run.finished_at, lang)}
        {" · "}{t(`trigger_${run.trigger}` as Key)} · {t("scanned")} {run.total}
      </div>

      {(run.status === "running" || run.status === "queued") && (
        <div className="panel stack" style={{ gap: 8 }}>
          <div className="progress"><div style={{ width: `${pct}%` }} /></div>
          <div className="muted small">{t("progress")} {run.done}/{run.total} {run.message}</div>
        </div>
      )}
      {run.error && <div className="panel error">{run.error}</div>}
      {run.failed.length > 0 && (
        <div className="panel small">
          <strong>{t("failedSymbols")} ({run.failed.length}):</strong>{" "}
          <span className="muted">{run.failed.join(" ")}</span>
        </div>
      )}

      {run.status === "done" && (
        <div className={`split${selected ? " with-chart" : ""}`}>
          <div className="panel table-wrap">
            {rows.length === 0 ? <div className="muted">{t("noResults")}</div> : (
              <>
                <div className="muted small" style={{ marginBottom: 8 }}>{t("chartHint")}</div>
                <table>
                  <thead>
                    <tr>
                      {multi && header("market", t("market"))}
                      {header("symbol", t("symbol"))}
                      {header("side", t("side"))}
                      {header("fractal_strength", t("strength"))}
                      {header("divergence", t("divType"))}
                      {header("divergence_score", t("score"), true)}
                      {header("rsi_diff", t("rsiDiff"), true)}
                      {header("price_change_pct", t("priceChange"), true)}
                      {header("rsi", "RSI", true)}
                      {header("close", t("close"), true)}
                      {header("date", t("date"))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.id} className={`clickable${selected?.id === r.id ? " selected" : ""}`}
                        onClick={() => setSelected(r)}>
                        {multi && <td><span className="badge">{MARKET_NAMES[r.market]?.[lang] ?? r.market}</span></td>}
                        <td><strong>{r.symbol}</strong> <span className="muted small">{r.name}</span></td>
                        <td><span className={`badge ${r.side === "bottom" ? "bull" : "bear"}`}>
                          {r.side === "bottom" ? "▲" : "▼"} {t(r.side)}</span></td>
                        <td>{r.fractal_strength
                          ? <span className={`badge s-${r.fractal_strength}`}>{t(r.fractal_strength as Key)}</span> : "—"}</td>
                        <td>{r.divergence ? t(`${r.divergence}Short` as Key) : "—"}</td>
                        <td className="num">{fmtNum(r.divergence_score)}</td>
                        <td className="num">{fmtNum(r.rsi_diff)}</td>
                        <td className="num">{fmtNum(r.price_change_pct)}</td>
                        <td className="num">{fmtNum(r.rsi)}</td>
                        <td className="num">{fmtNum(r.close)}</td>
                        <td className="small">{r.date}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
          {selected && (
            <div className="panel">
              <Chart market={selected.market || run.markets[0]} symbol={selected.symbol} timeframe={run.timeframe} runId={run.id}
                title={`${selected.symbol} ${selected.name}`} onClose={() => setSelected(null)} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
