const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type FeedMode = "inefficiency" | "volume_scan" | "all";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; disclaimer: string }>("/health"),
  marketStatus: () => request<import("@/types").MarketStatus>("/api/v1/market/status"),
  signals: (minScore = 0, feed: FeedMode = "inefficiency") =>
    request<import("@/types").Signal[]>(
      `/api/v1/signals?min_score=${minScore}&limit=50&feed=${feed}`
    ),
  signal: (id: number) => request<import("@/types").Signal>(`/api/v1/signals/${id}`),
  scannerTop: (minScore = 0, feed: FeedMode = "inefficiency") =>
    request<{
      smc_setups: import("@/types").Signal[];
      pump_candidates: import("@/types").Signal[];
      disclaimer: string;
    }>(`/api/v1/scanner/top?min_score=${minScore}&feed=${feed}`),
  charts: (symbol: string, timeframe = "15") =>
    request<{ symbol: string; timeframe: string; candles: import("@/types").Candle[] }>(
      `/api/v1/charts/${symbol}?timeframe=${timeframe}&limit=200`
    ),
  runScan: (limit = 15, mode: "all" | "bybit" = "all") =>
    request<{ created: number; feed?: string; note?: string }>(
      `/api/v1/scanner/run?limit=${limit}&mode=${mode}`,
      { method: "POST" }
    ),
  backtest: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>("/api/v1/backtest/run", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  aiExplain: (signalId: number, mode: string = "explain") =>
    request<Record<string, unknown>>("/api/v1/ai/explain", {
      method: "POST",
      body: JSON.stringify({ signal_id: signalId, mode }),
    }),
  aiPlan: (signalId: number) =>
    request<Record<string, unknown>>("/api/v1/ai/plan", {
      method: "POST",
      body: JSON.stringify({ signal_id: signalId, mode: "plan" }),
    }),
  aiMarket: (symbol: string) =>
    request<Record<string, unknown>>("/api/v1/ai/market-analysis", {
      method: "POST",
      body: JSON.stringify({ symbol }),
    }),
  dataHealth: () => request<Record<string, unknown>>("/api/v1/data/health"),
  feedback: (signalId: number, vote: "up" | "down" | "skip") =>
    request<{ ok: boolean }>("/api/v1/notifications/feedback", {
      method: "POST",
      body: JSON.stringify({ signal_id: signalId, vote }),
    }),
  exchangeStatus: () =>
    request<{ exchanges: Array<Record<string, unknown>> }>("/api/v1/exchanges/status"),
  exchangeUniverse: (minVolume = 1_000_000) =>
    request<{ count: number; symbols: Array<Record<string, unknown>> }>(
      `/api/v1/exchanges/universe?min_volume=${minVolume}&limit=50`
    ),
  lowcap: () =>
    request<{ count: number; candidates: Array<Record<string, unknown>> }>(
      "/api/v1/exchanges/lowcap?limit=30"
    ),
  newListings: () =>
    request<{ count: number; listings: Array<Record<string, unknown>> }>(
      "/api/v1/exchanges/new-listings"
    ),
  pumpHunter: (analyzeTop = 20) =>
    request<{
      count: number;
      candidates: Array<Record<string, unknown>>;
      disclaimer: string;
      params?: Record<string, unknown>;
    }>(
      `/api/v1/pump-hunter?analyze_top=${analyzeTop}&min_score=50&min_volume=500000&max_volume=25000000`
    ),
  createTradePlan: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>("/api/v1/trade-plan/create", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  mlAnalyze: (symbol: string, exchange = "bybit") =>
    request<Record<string, unknown>>("/api/v1/ml/analyze", {
      method: "POST",
      body: JSON.stringify({ symbol, exchange, timeframe: "15m" }),
    }),
  terminalBundle: async (symbol: string, exchange = "bybit") => {
    const [chart, plan, ml] = await Promise.all([
      request<{ candles: import("@/types").Candle[] }>(
        `/api/v1/charts/${symbol}?timeframe=15&limit=200`
      ),
      request<Record<string, unknown>>("/api/v1/trade-plan/create", {
        method: "POST",
        body: JSON.stringify({ symbol, exchange, timeframe: "15m" }),
      }),
      request<Record<string, unknown>>("/api/v1/ml/analyze", {
        method: "POST",
        body: JSON.stringify({ symbol, exchange, timeframe: "15m" }),
      }),
    ]);
    return { chart, plan, ml };
  },
  universeRun: (opts?: { cheap_limit?: number; heavy_limit?: number; do_heavy?: boolean }) => {
    const cheap = opts?.cheap_limit ?? 150;
    const heavy = opts?.heavy_limit ?? 30;
    const doHeavy = opts?.do_heavy ?? true;
    return request<Record<string, unknown>>(
      `/api/v1/universe/run?cheap_limit=${cheap}&heavy_limit=${heavy}&do_heavy=${doHeavy}&trade_ideas=15`,
      { method: "POST" }
    );
  },
  universeIdeas: () =>
    request<{ count: number; ideas: Array<Record<string, unknown>> }>("/api/v1/universe/ideas"),
  universeSnapshot: () => request<Record<string, unknown>>("/api/v1/universe/snapshot"),
  entryEvaluate: (symbol: string, exchange = "bybit", mode: string = "balanced") =>
    request<Record<string, unknown>>("/api/v1/entry/evaluate", {
      method: "POST",
      body: JSON.stringify({ symbol, exchange, mode, timeframe: "15m" }),
    }),
  journalList: (limit = 50) =>
    request<
      Array<{
        id: number;
        symbol: string;
        side: string;
        entry_price?: number | null;
        exit_price?: number | null;
        pnl?: number | null;
        result?: string | null;
        meta?: Record<string, unknown>;
      }>
    >(`/api/v1/journal?limit=${limit}&setup=inefficiency`),
  journalStats: () =>
    request<{
      closed: number;
      wins: number;
      losses: number;
      winrate: number | null;
      avg_r: number | null;
      usable_for_edge: boolean;
      by_type?: Record<string, unknown>;
    }>("/api/v1/journal/stats?setup=inefficiency"),
  journalCreate: (body: Record<string, unknown>) =>
    request<Record<string, unknown>>("/api/v1/journal", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
