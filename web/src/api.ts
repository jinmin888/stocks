export type Market = "crypto" | "kr" | "cn" | "us" | "hk";

export interface ScreenConfig {
  fractal: {
    enabled: boolean; inclusion: boolean; strict_bi: boolean; recent_bars: number;
    min_strength: number | null; confirm_k4: boolean; volume_check: boolean; volume_ma: number;
  };
  divergence: {
    enabled: boolean; rsi_period: number; regular: boolean; hidden: boolean;
    min_gap: number; max_gap: number; oversold: number | null; overbought: number | null;
    recent_bars: number; min_fractal_strength: number | null;
    min_price_change_pct: number | null; min_rsi_diff: number | null;
    score_rsi_weight: number; score_price_weight: number;
  };
  logic: "and" | "or";
  direction: "bottom" | "top" | "both";
  filters: {
    exclude_st: boolean; exclude_etf: boolean; min_list_days: number | null;
    min_market_cap: Record<string, number | null>; min_turnover: Record<string, number | null>;
    exclude_tokenized: boolean; extra_tokenized: string[];
  };
  display_tz: string;
}

export interface Run {
  id: number; task_id: number | null; trigger: string;
  status: "queued" | "running" | "done" | "failed";
  started_at: string | null; finished_at: string | null; created_at: string;
  total: number; done: number; message: string; error: string | null; failed: string[];
  result_count: number; task_name: string | null; markets: Market[]; timeframe: string;
}

export interface TaskInput {
  name: string; markets: Market[]; universes: Partial<Record<Market, string | null>>;
  symbols_by_market: Partial<Record<Market, string[]>>; timeframe: string; exchange: string;
  config: ScreenConfig; cron: string | null; timezone: string; enabled: boolean; notify: boolean;
}
export interface Task extends TaskInput {
  id: number; last_run: Run | null; next_run: string | null;
}

export interface ResultRow {
  id: number; market: Market; symbol: string; name: string; side: "bottom" | "top"; date: string; close: number;
  rsi: number | null; fractal_strength: string | null; divergence: string | null;
  divergence_score: number | null; price_change_pct: number | null; rsi_diff: number | null;
}
export interface RunDetail extends Run { results: ResultRow[]; snapshot: TaskInput }

export interface Meta {
  markets: Record<Market, { timeframes: string[]; universes: string[]; exchanges?: string[] }>;
  default_universe: Record<Market, string>;
  default_schedule: Record<string, { cron: string; timezone: string }>;
  default_config: ScreenConfig;
}

export interface ChartPoint { time: number; price: number; rsi?: number }
export interface ChartData {
  symbol: string; market: Market; timeframe: string;
  bars: { time: number; open: number; high: number; low: number; close: number; volume: number }[];
  rsi: { time: number; value: number }[];
  fractals: (ChartPoint & { type: "top" | "bottom"; strength: string; confirm_time: number })[];
  divergences: { side: "top" | "bottom"; kind: string; score: number; from: ChartPoint; to: ChartPoint }[];
  config: { rsi_period: number; oversold: number | null; overbought: number | null };
}

export interface KakaoStatus {
  configured: boolean; connected: boolean; refresh_expires_at: string | null;
  redirect_uri: string; lang: string;
}

export interface SignalDate { date: string; count: number; bottom: number; top: number }
export interface SignalRow extends ResultRow {
  timeframe: string; run_id: number; tasks: string[]; found_at: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function req<T>(method: string, url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method,
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    credentials: "same-origin",
  });
  if (!r.ok) {
    let msg = r.statusText;
    try {
      const j = await r.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch { /* ignore */ }
    if (r.status === 401 && !url.endsWith("/login")) window.dispatchEvent(new Event("unauthorized"));
    throw new ApiError(r.status, msg);
  }
  return r.json();
}

export const api = {
  login: (username: string, password: string) => req<{ user: string }>("POST", "/api/login", { username, password }),
  logout: () => req("POST", "/api/logout"),
  me: () => req<{ user: string }>("GET", "/api/me"),
  meta: () => req<Meta>("GET", "/api/meta"),
  tasks: () => req<Task[]>("GET", "/api/tasks"),
  task: (id: number) => req<Task>("GET", `/api/tasks/${id}`),
  createTask: (t: TaskInput) => req<Task>("POST", "/api/tasks", t),
  updateTask: (id: number, t: TaskInput) => req<Task>("PUT", `/api/tasks/${id}`, t),
  deleteTask: (id: number) => req("DELETE", `/api/tasks/${id}`),
  runTask: (id: number) => req<{ run_id: number }>("POST", `/api/tasks/${id}/run`),
  runs: (taskId?: number) => req<Run[]>("GET", `/api/runs${taskId ? `?task_id=${taskId}` : ""}`),
  run: (id: number) => req<RunDetail>("GET", `/api/runs/${id}`),
  signalDates: () => req<SignalDate[]>("GET", "/api/signals/dates"),
  signals: (date: string) => req<SignalRow[]>("GET", `/api/signals?date=${encodeURIComponent(date)}`),
  kakaoStatus: () => req<KakaoStatus>("GET", "/api/kakao/status"),
  kakaoTest: () => req("POST", "/api/kakao/test"),
  kakaoDisconnect: () => req("DELETE", "/api/kakao"),
  chart: (p: { market: string; symbol: string; timeframe: string; run_id?: number }) => {
    const q = new URLSearchParams({ market: p.market, symbol: p.symbol, timeframe: p.timeframe });
    if (p.run_id) q.set("run_id", String(p.run_id));
    return req<ChartData>("GET", `/api/chart?${q}`);
  },
};
