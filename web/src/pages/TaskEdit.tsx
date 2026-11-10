import { useEffect, useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type Market, type Meta, type ScreenConfig, type TaskInput } from "../api";
import { MARKET_NAMES, UNIVERSE_NAMES, useI18n } from "../i18n";

const TIMEZONES = ["Asia/Seoul", "Asia/Shanghai", "Asia/Hong_Kong", "America/New_York", "UTC"];

function scheduleFor(meta: Meta, market: Market, timeframe: string) {
  return meta.default_schedule[`${market}:${timeframe}`] ?? meta.default_schedule[market]
    ?? { cron: "", timezone: "Asia/Seoul" };
}

const ALL_MARKETS: Market[] = ["crypto", "kr", "cn", "us", "hk"];
const PLACEHOLDER: Record<Market, string> = {
  crypto: "BTC/USDT ETH/USDT", kr: "005930 000660", cn: "600519 000858", us: "AAPL NVDA", hk: "0700.HK 9988.HK",
};

/** 所有已选市场都支持的周期 */
function commonTimeframes(meta: Meta, markets: Market[]): string[] {
  if (!markets.length) return [];
  return meta.markets[markets[0]].timeframes.filter((tf) => markets.every((m) => meta.markets[m].timeframes.includes(tf)));
}

function blank(meta: Meta): TaskInput {
  const s = scheduleFor(meta, "crypto", "4h");
  return {
    name: "", markets: ["crypto"], universes: { crypto: meta.default_universe.crypto }, symbols_by_market: {},
    timeframe: "4h", exchange: "binance", config: structuredClone(meta.default_config), cron: s.cron,
    timezone: s.timezone, enabled: true, notify: true,
  };
}

/** 数字输入；allowNull 时留空表示关闭 */
function Num({ value, onChange, allowNull, step = 1, min }: {
  value: number | null; onChange: (v: number | null) => void; allowNull?: boolean; step?: number; min?: number;
}) {
  return (
    <input type="number" step={step} min={min} value={value ?? ""}
      onChange={(e) => {
        const raw = e.target.value;
        if (raw === "") { if (allowNull) onChange(null); return; }
        const n = Number(raw);
        if (!Number.isNaN(n)) onChange(n);
      }} />
  );
}

function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return <label className="field"><span>{label}</span>{children}{hint && <span className="small">{hint}</span>}</label>;
}

function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="check">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />{label}
    </label>
  );
}

export default function TaskEdit({ meta }: { meta: Meta }) {
  const { t, lang } = useI18n();
  const { id } = useParams();
  const nav = useNavigate();
  const [task, setTask] = useState<TaskInput | null>(id ? null : blank(meta));
  const [symbolsText, setSymbolsText] = useState<Partial<Record<Market, string>>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!id) return;
    api.task(Number(id)).then((x) => {
      const { id: _i, last_run: _l, next_run: _n, ...rest } = x;
      setTask(rest);
      setSymbolsText(Object.fromEntries(Object.entries(x.symbols_by_market).map(([k, v]) => [k, (v ?? []).join("\n")])));
    }).catch((e) => setError(e.message));
  }, [id]);

  if (!task) return <div className="muted">{error || t("loading")}</div>;

  const set = (patch: Partial<TaskInput>) => setTask({ ...task, ...patch });
  const cfg = task.config;
  const setCfg = (fn: (c: ScreenConfig) => void) => {
    const c = structuredClone(cfg);
    fn(c);
    set({ config: c });
  };
  const timeframes = commonTimeframes(meta, task.markets);
  const has = (m: Market) => task.markets.includes(m);
  const stockMarkets = task.markets.filter((m) => m !== "crypto");
  const strengthOpts = (
    <>
      <option value="">{t("any")}</option>
      <option value="2">{t("medium")}+</option>
      <option value="3">{t("strong")}</option>
    </>
  );

  const toggleMarket = (market: Market, on: boolean) => {
    // 保持固定顺序；至少保留一个市场
    const markets = ALL_MARKETS.filter((m) => (m === market ? on : task.markets.includes(m)));
    if (!markets.length) return;
    const tfs = commonTimeframes(meta, markets);
    if (!tfs.length) {
      setError(t("noCommonTimeframe"));
      return;
    }
    setError("");
    const timeframe = tfs.includes(task.timeframe) ? task.timeframe : tfs[0];
    const universes = { ...task.universes };
    if (on && !universes[market]) universes[market] = meta.default_universe[market];
    const patch: Partial<TaskInput> = { markets, timeframe, universes };
    // 第一个市场变化或周期变化时，换成对应的建议定时
    if (markets[0] !== task.markets[0] || timeframe !== task.timeframe) {
      const sch = scheduleFor(meta, markets[0], timeframe);
      Object.assign(patch, { cron: sch.cron, timezone: sch.timezone });
    }
    set(patch);
  };
  const changeTimeframe = (timeframe: string) => {
    const s = scheduleFor(meta, task.markets[0], timeframe);
    set({ timeframe, cron: s.cron, timezone: s.timezone });
  };

  const save = async () => {
    setBusy(true);
    setError("");
    const body: TaskInput = {
      ...task,
      name: task.name.trim() || `${task.markets.map((m) => MARKET_NAMES[m][lang]).join("+")} ${task.timeframe}`,
      symbols_by_market: Object.fromEntries(task.markets.map((m) => [m,
        (symbolsText[m] ?? "").split(/[\s,]+/).map((x) => x.trim()).filter(Boolean)])),
      cron: task.cron?.trim() || null,
    };
    try {
      if (id) await api.updateTask(Number(id), body);
      else await api.createTask(body);
      nav("/tasks");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <h1>{id ? t("editTask") : t("newTask")}</h1>

      <div className="panel stack">
        <div className="form-grid">
          <Field label={t("name")}>
            <input value={task.name} onChange={(e) => set({ name: e.target.value })} />
          </Field>
          <Field label={t("timeframe")} hint={task.markets.length > 1 ? t("timeframeCommonHint") : undefined}>
            <select value={task.timeframe} onChange={(e) => changeTimeframe(e.target.value)}>
              {timeframes.map((tf) => <option key={tf}>{tf}</option>)}
            </select>
          </Field>
        </div>
        <div className="field">
          <span>{t("market")}</span>
          <div className="row" style={{ gap: 16 }}>
            {ALL_MARKETS.map((m) => (
              <Check key={m} label={MARKET_NAMES[m][lang]} checked={has(m)} onChange={(v) => toggleMarket(m, v)} />
            ))}
          </div>
        </div>
        <div className="market-grid">
          {task.markets.map((m) => {
            const mk = meta.markets[m];
            const uni = task.universes[m] ?? meta.default_universe[m];
            return (
              <div className="market-card stack" key={m}>
                <strong>{MARKET_NAMES[m][lang]}</strong>
                <div className="row">
                  <Field label={t("universe")}>
                    <select value={uni} onChange={(e) => set({ universes: { ...task.universes, [m]: e.target.value } })}>
                      {[...mk.universes, ...(mk.universes.includes(uni) ? [] : [uni])]
                        .map((u) => <option key={u} value={u}>{UNIVERSE_NAMES[u]?.[lang] ?? u}</option>)}
                    </select>
                  </Field>
                  {mk.exchanges && (
                    <Field label={t("exchange")}>
                      <select value={task.exchange} onChange={(e) => set({ exchange: e.target.value })}>
                        {mk.exchanges.map((x) => <option key={x}>{x}</option>)}
                      </select>
                    </Field>
                  )}
                </div>
                <Field label={t("customSymbols")}>
                  <textarea value={symbolsText[m] ?? ""} placeholder={PLACEHOLDER[m]}
                    onChange={(e) => setSymbolsText({ ...symbolsText, [m]: e.target.value })} />
                </Field>
              </div>
            );
          })}
        </div>
        <div className="muted small">{t("symbolsHint")}</div>
      </div>

      <fieldset className="panel">
        <legend>{t("schedule")}</legend>
        <div className="form-grid">
          <Field label={t("cron")} hint={t("cronHint")}>
            <div className="row">
              <input value={task.cron ?? ""} onChange={(e) => set({ cron: e.target.value })}
                style={{ flex: 1, minWidth: 150, fontFamily: "monospace" }} />
              <button type="button" onClick={() => {
                const s = scheduleFor(meta, task.markets[0], task.timeframe);
                set({ cron: s.cron, timezone: s.timezone });
              }}>{t("useDefault")}</button>
            </div>
          </Field>
          <Field label={t("timezone")}>
            <select value={task.timezone} onChange={(e) => set({ timezone: e.target.value })}>
              {TIMEZONES.map((z) => <option key={z}>{z}</option>)}
            </select>
          </Field>
          <div className="stack" style={{ gap: 6, justifyContent: "center" }}>
            <Check label={t("enabled")} checked={task.enabled} onChange={(v) => set({ enabled: v })} />
            <Check label={t("notify")} checked={task.notify} onChange={(v) => set({ notify: v })} />
          </div>
        </div>
      </fieldset>

      <div className="panel stack">
        <h2>{t("conditions")}</h2>
        <div className="form-grid">
          <Field label={t("combine")}>
            <select value={cfg.logic} onChange={(e) => setCfg((c) => { c.logic = e.target.value as "and" | "or"; })}>
              <option value="and">{t("logicAnd")}</option>
              <option value="or">{t("logicOr")}</option>
            </select>
          </Field>
          <Field label={t("direction")}>
            <select value={cfg.direction}
              onChange={(e) => setCfg((c) => { c.direction = e.target.value as ScreenConfig["direction"]; })}>
              <option value="both">{t("both")}</option>
              <option value="bottom">{t("bottom")}</option>
              <option value="top">{t("top")}</option>
            </select>
          </Field>
        </div>

        <fieldset disabled={!cfg.fractal.enabled}>
          <legend>
            <label className="check">
              <input type="checkbox" checked={cfg.fractal.enabled} disabled={false}
                onChange={(e) => setCfg((c) => { c.fractal.enabled = e.target.checked; })} />
              {t("fractal")}
            </label>
          </legend>
          <div className="form-grid">
            <Check label={t("inclusion")} checked={cfg.fractal.inclusion}
              onChange={(v) => setCfg((c) => { c.fractal.inclusion = v; })} />
            <Check label={t("strictBi")} checked={cfg.fractal.strict_bi}
              onChange={(v) => setCfg((c) => { c.fractal.strict_bi = v; })} />
            <Field label={t("recentBars")}>
              <Num min={1} value={cfg.fractal.recent_bars}
                onChange={(v) => setCfg((c) => { c.fractal.recent_bars = v ?? 1; })} />
            </Field>
            <Field label={t("minStrength")}>
              <select value={cfg.fractal.min_strength ?? ""}
                onChange={(e) => setCfg((c) => { c.fractal.min_strength = e.target.value ? Number(e.target.value) : null; })}>
                {strengthOpts}
              </select>
            </Field>
            <Check label={t("confirmK4")} checked={cfg.fractal.confirm_k4}
              onChange={(v) => setCfg((c) => { c.fractal.confirm_k4 = v; })} />
            <Check label={t("volumeCheck")} checked={cfg.fractal.volume_check}
              onChange={(v) => setCfg((c) => { c.fractal.volume_check = v; })} />
            {cfg.fractal.volume_check && (
              <Field label={t("volumeMa")}>
                <Num min={1} value={cfg.fractal.volume_ma}
                  onChange={(v) => setCfg((c) => { c.fractal.volume_ma = v ?? 5; })} />
              </Field>
            )}
          </div>
        </fieldset>

        <fieldset disabled={!cfg.divergence.enabled}>
          <legend>
            <label className="check">
              <input type="checkbox" checked={cfg.divergence.enabled} disabled={false}
                onChange={(e) => setCfg((c) => { c.divergence.enabled = e.target.checked; })} />
              {t("divergence")}
            </label>
          </legend>
          <div className="form-grid">
            <Field label={t("rsiPeriod")}>
              <Num min={2} value={cfg.divergence.rsi_period}
                onChange={(v) => setCfg((c) => { c.divergence.rsi_period = v ?? 14; })} />
            </Field>
            <div className="stack" style={{ gap: 6 }}>
              <Check label={t("regular")} checked={cfg.divergence.regular}
                onChange={(v) => setCfg((c) => { c.divergence.regular = v; })} />
              <Check label={t("hidden")} checked={cfg.divergence.hidden}
                onChange={(v) => setCfg((c) => { c.divergence.hidden = v; })} />
            </div>
            <Field label={`${t("minGap")} / ${t("maxGap")}`}>
              <div className="row">
                <Num min={1} value={cfg.divergence.min_gap}
                  onChange={(v) => setCfg((c) => { c.divergence.min_gap = v ?? 5; })} />
                <Num min={1} value={cfg.divergence.max_gap}
                  onChange={(v) => setCfg((c) => { c.divergence.max_gap = v ?? 60; })} />
              </div>
            </Field>
            <Field label={`${t("oversold")} / ${t("overbought")}`} hint={t("emptyOff")}>
              <div className="row">
                <Num allowNull value={cfg.divergence.oversold}
                  onChange={(v) => setCfg((c) => { c.divergence.oversold = v; })} />
                <Num allowNull value={cfg.divergence.overbought}
                  onChange={(v) => setCfg((c) => { c.divergence.overbought = v; })} />
              </div>
            </Field>
            <Field label={t("recentBars")}>
              <Num min={1} value={cfg.divergence.recent_bars}
                onChange={(v) => setCfg((c) => { c.divergence.recent_bars = v ?? 3; })} />
            </Field>
            <Field label={t("minFractalStrength")}>
              <select value={cfg.divergence.min_fractal_strength ?? ""}
                onChange={(e) => setCfg((c) => {
                  c.divergence.min_fractal_strength = e.target.value ? Number(e.target.value) : null;
                })}>
                {strengthOpts}
              </select>
            </Field>
            <Field label={t("minPriceChange")} hint={t("emptyOff")}>
              <Num allowNull step={0.1} value={cfg.divergence.min_price_change_pct}
                onChange={(v) => setCfg((c) => { c.divergence.min_price_change_pct = v; })} />
            </Field>
            <Field label={t("minRsiDiff")} hint={t("emptyOff")}>
              <Num allowNull step={0.5} value={cfg.divergence.min_rsi_diff}
                onChange={(v) => setCfg((c) => { c.divergence.min_rsi_diff = v; })} />
            </Field>
            <Field label={t("scoreWeights")}>
              <div className="row">
                <Num step={0.1} value={cfg.divergence.score_rsi_weight}
                  onChange={(v) => setCfg((c) => { c.divergence.score_rsi_weight = v ?? 1; })} />
                <Num step={0.1} value={cfg.divergence.score_price_weight}
                  onChange={(v) => setCfg((c) => { c.divergence.score_price_weight = v ?? 0.2; })} />
              </div>
            </Field>
          </div>
        </fieldset>

        <fieldset>
          <legend>{t("filters")}</legend>
          <div className="form-grid">
            {has("cn") && (
              <Check label={t("excludeSt")} checked={cfg.filters.exclude_st}
                onChange={(v) => setCfg((c) => { c.filters.exclude_st = v; })} />
            )}
            {stockMarkets.length > 0 && (
              <>
                <Check label={t("excludeEtf")} checked={cfg.filters.exclude_etf}
                  onChange={(v) => setCfg((c) => { c.filters.exclude_etf = v; })} />
                <Field label={t("minListDays")} hint={t("emptyOff")}>
                  <Num allowNull min={0} value={cfg.filters.min_list_days}
                    onChange={(v) => setCfg((c) => { c.filters.min_list_days = v; })} />
                </Field>
              </>
            )}
            {stockMarkets.map((m) => (
              <Field key={m} label={`${t("minMarketCap")} · ${MARKET_NAMES[m][lang]}`} hint={t("emptyOff")}>
                <input type="number" style={{ width: 160 }}
                  value={cfg.filters.min_market_cap[m] ?? ""}
                  onChange={(e) => setCfg((c) => {
                    c.filters.min_market_cap[m] = e.target.value === "" ? null : Number(e.target.value);
                  })} />
              </Field>
            ))}
            {has("crypto") && (
              <Check label={t("excludeTokenized")} checked={cfg.filters.exclude_tokenized}
                onChange={(v) => setCfg((c) => { c.filters.exclude_tokenized = v; })} />
            )}
          </div>
        </fieldset>
      </div>

      {error && <div className="error">{error}</div>}
      <div className="row">
        <button className="primary" onClick={save} disabled={busy}>{t("save")}</button>
        <button onClick={() => nav(-1)}>{t("cancel")}</button>
      </div>
    </div>
  );
}
