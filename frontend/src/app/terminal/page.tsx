"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { api } from "@/services/api";
import { PriceChart } from "@/components/charts/PriceChart";

const STATUS_COLOR: Record<string, string> = {
  WATCH: "text-mist",
  SETUP_FORMING: "text-warn",
  APPROACHING_ENTRY: "text-warn",
  ENTRY_READY: "text-accent",
  MISSED: "text-warn",
  INVALIDATED: "text-[#FF4444]",
};

function TerminalInner() {
  const search = useSearchParams();
  const [symbol, setSymbol] = useState((search.get("symbol") || "BTCUSDT").toUpperCase());
  const [exchange, setExchange] = useState(search.get("exchange") || "bybit");
  const [mode, setMode] = useState<"conservative" | "balanced" | "aggressive">("balanced");
  const [tf] = useState("15");

  const chartQ = useQuery({
    queryKey: ["terminal-chart", symbol, tf],
    queryFn: () => api.charts(symbol, tf),
    retry: 1,
    staleTime: 30_000,
  });

  const entryQ = useQuery({
    queryKey: ["entry-assistant", symbol, exchange, mode],
    queryFn: () => api.entryEvaluate(symbol, exchange, mode),
    retry: 1,
    staleTime: 20_000,
  });

  const load = useMutation({
    mutationFn: async () => {
      const [bundle, entry] = await Promise.all([
        api.terminalBundle(symbol, exchange),
        api.entryEvaluate(symbol, exchange, mode),
      ]);
      return { ...bundle, entry };
    },
  });

  useEffect(() => {
    const s = search.get("symbol");
    if (s) setSymbol(s.toUpperCase());
    const ex = search.get("exchange");
    if (ex) setExchange(ex);
  }, [search]);

  const plan = (load.data?.plan || undefined) as Record<string, unknown> | undefined;
  const ml = load.data?.ml as {
    decision?: Record<string, unknown>;
  } | undefined;

  const candles = load.data?.chart?.candles?.length
    ? load.data.chart.candles
    : chartQ.data?.candles || [];

  const entry = (load.data?.entry || entryQ.data || {}) as Record<string, unknown>;
  const triggers = (entry.triggers || {}) as Record<
    string,
    { ok?: boolean; label_ru?: string }
  >;
  const zone = (entry.entry_zone || {}) as { low?: number; high?: number };
  const targets = (entry.targets || {}) as { tp1?: number; tp2?: number };
  const liq = (entry.liquidity_map || {}) as Record<string, unknown>;

  const zones = useMemo(() => [], []);
  const decision = ml?.decision || {};
  const status = String(entry.status || "");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-mist">Торговый терминал</p>
          <h1 className="font-display text-3xl md:text-4xl">{symbol}</h1>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <input
            className="rounded-md bg-ink border border-line px-3 py-2 text-sm"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                chartQ.refetch();
                entryQ.refetch();
              }
            }}
          />
          <select
            className="rounded-md bg-ink border border-line px-3 py-2 text-sm"
            value={exchange}
            onChange={(e) => setExchange(e.target.value)}
          >
            {["bybit", "okx", "bitget", "mexc", "bingx", "kucoin"].map((e) => (
              <option key={e} value={e}>
                {e}
              </option>
            ))}
          </select>
          <select
            className="rounded-md bg-ink border border-line px-3 py-2 text-sm"
            value={mode}
            onChange={(e) => setMode(e.target.value as typeof mode)}
            title="Режим подтверждения входа"
          >
            <option value="conservative">Conservative</option>
            <option value="balanced">Balanced</option>
            <option value="aggressive">Aggressive</option>
          </select>
          <button
            type="button"
            onClick={() => {
              chartQ.refetch();
              entryQ.refetch();
            }}
            disabled={chartQ.isFetching || entryQ.isFetching}
            className="rounded-md border border-line px-3 py-2 text-sm hover:border-accent disabled:opacity-50"
          >
            Обновить
          </button>
          <button
            type="button"
            onClick={() => load.mutate()}
            disabled={load.isPending}
            className="rounded-md bg-accent px-4 py-2 text-ink text-sm font-medium disabled:opacity-50"
          >
            {load.isPending ? "Загрузка…" : "Полный анализ"}
          </button>
        </div>
      </div>

      {(chartQ.isError || entryQ.isError || load.isError) && (
        <div className="rounded-lg border border-warn/40 bg-warn/10 p-3 text-sm">
          Ошибка загрузки. Проверьте API (8000) и доступ к бирже.
        </div>
      )}

      <div className="grid lg:grid-cols-[1.5fr_1fr] gap-4">
        <div className="space-y-3">
          <PriceChart
            candles={candles}
            zones={zones}
            emptyHint={
              chartQ.isFetching ? "Загрузка свечей…" : "Нет свечей для этого символа"
            }
          />
          <div className="flex flex-wrap gap-2">
            {["LONG", "SHORT", "Лимит", "Отмена"].map((b) => (
              <button
                key={b}
                type="button"
                disabled={status !== "ENTRY_READY"}
                className="rounded-md border border-line px-3 py-2 text-sm hover:border-accent disabled:opacity-40"
                title={
                  status === "ENTRY_READY"
                    ? "Режим подтверждения — ордер вручную"
                    : "Доступно только при статусе ENTRY READY"
                }
              >
                {b}
              </button>
            ))}
          </div>
          <p className="text-xs text-mist">
            Вход вручную только при ENTRY READY. Автоордера выключены.
            {candles.length ? ` · свечей: ${candles.length}` : ""}
          </p>
        </div>

        <div className="space-y-4">
          {/* AI Entry Assistant */}
          <div className="rounded-xl border border-line bg-panel/60 p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-display text-xl">AI Entry Assistant</h2>
              {entryQ.isFetching && <span className="text-xs text-mist">обновление…</span>}
            </div>

            {entry.status ? (
              <>
                <div>
                  <div className="text-xs uppercase tracking-wider text-mist">Статус сделки</div>
                  <div className={`font-display text-2xl mt-1 ${STATUS_COLOR[status] || ""}`}>
                    {String(entry.status_ru || status)}
                  </div>
                  <p className="text-sm text-mist mt-1">{String(entry.action || "")}</p>
                </div>

                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-md bg-ink/50 p-2">
                    <div className="text-xs text-mist">Фаза</div>
                    <div>{String(entry.phase_ru || entry.phase || "—")}</div>
                  </div>
                  <div className="rounded-md bg-ink/50 p-2">
                    <div className="text-xs text-mist">Вероятность</div>
                    <div>{String(entry.probability ?? "—")}%</div>
                  </div>
                  <div className="rounded-md bg-ink/50 p-2">
                    <div className="text-xs text-mist">Направление</div>
                    <div>{String(entry.direction || "—")}</div>
                  </div>
                  <div className="rounded-md bg-ink/50 p-2">
                    <div className="text-xs text-mist">До зоны</div>
                    <div>
                      {entry.distance_pct != null
                        ? `${Number(entry.distance_pct) > 0 ? "+" : ""}${entry.distance_pct}%`
                        : "—"}
                    </div>
                  </div>
                </div>

                <div className="text-sm">
                  <div className="text-xs text-mist mb-1">Этап</div>
                  <p>{String(entry.current_stage || "—")}</p>
                </div>

                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-md bg-ink/50 p-2">
                    <div className="text-xs text-mist">Зона входа</div>
                    <div>
                      {zone.low != null && zone.high != null
                        ? `${zone.low} – ${zone.high}`
                        : "—"}
                    </div>
                  </div>
                  <div className="rounded-md bg-ink/50 p-2">
                    <div className="text-xs text-mist">Сейчас</div>
                    <div>{String(entry.current_price ?? "—")}</div>
                  </div>
                  <div className="rounded-md bg-ink/50 p-2">
                    <div className="text-xs text-mist">Стоп</div>
                    <div>{String(entry.stop ?? "—")}</div>
                  </div>
                  <div className="rounded-md bg-ink/50 p-2">
                    <div className="text-xs text-mist">TP1 / TP2 · RR</div>
                    <div>
                      {targets.tp1 ?? "—"} / {targets.tp2 ?? "—"} · {String(entry.risk_reward ?? "—")}
                    </div>
                  </div>
                </div>

                <div>
                  <div className="text-xs text-mist mb-2">Триггеры ({mode})</div>
                  <ul className="space-y-1 text-sm">
                    {Object.entries(triggers).map(([key, t]) => {
                      const needed = ((entry.triggers_needed as string[]) || []).includes(key);
                      if (!needed && mode !== "balanced") {
                        // show all for transparency on balanced; for others show needed + ok ones
                      }
                      const show =
                        needed || t.ok || ["liquidity_sweep", "choch", "bos", "volume"].includes(key);
                      if (!show) return null;
                      return (
                        <li key={key} className="flex gap-2">
                          <span>{t.ok ? "✅" : "⏳"}</span>
                          <span className={needed && !t.ok ? "text-warn" : ""}>
                            {t.label_ru || key}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </div>

                {liq.note_ru ? (
                  <p className="text-xs text-mist border-t border-line/60 pt-2">
                    Карта ликвидности: {String(liq.note_ru)}
                    {liq.liquidity_below != null ? ` · пул снизу ≈ ${liq.liquidity_below}` : ""}
                    {liq.liquidity_above != null ? ` · пул сверху ≈ ${liq.liquidity_above}` : ""}
                  </p>
                ) : null}
              </>
            ) : (
              <p className="text-sm text-mist">Загрузка Entry Assistant…</p>
            )}
          </div>

          <div className="rounded-xl border border-line bg-panel/60 p-4">
            <h2 className="font-display text-xl">Quant / Decision</h2>
            {ml ? (
              <div className="mt-3 text-sm space-y-2">
                <p>
                  AI Score: <span className="text-accent text-lg">{String(decision.ai_score)}</span> ·{" "}
                  {String(decision.action)}
                </p>
                <p className="text-xs text-mist">{String(decision.disclaimer)}</p>
              </div>
            ) : (
              <p className="text-mist text-sm mt-2">Нажмите «Полный анализ» для Quant.</p>
            )}
          </div>

          <div className="rounded-xl border border-line bg-panel/60 p-4">
            <h2 className="font-display text-xl">Торговый план</h2>
            {plan ? (
              <div className="mt-3 text-sm space-y-2">
                <p className="text-mist">{String(plan.setup_label || plan.setup)}</p>
                <p>
                  {String(plan.direction)} · RR {String(plan.risk_reward)}
                </p>
              </div>
            ) : (
              <p className="text-mist text-sm mt-2">План появится после полного анализа.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function TerminalPage() {
  return (
    <Suspense fallback={<p className="text-mist">Загрузка терминала…</p>}>
      <TerminalInner />
    </Suspense>
  );
}
