"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { api } from "@/services/api";
import { SignalCard } from "@/components/cards/SignalCard";

function rankOpportunity(
  a: import("@/types").Signal,
  b: import("@/types").Signal
): number {
  const ae = a.edge_score ?? 0;
  const be = b.edge_score ?? 0;
  if (be !== ae) return be - ae;
  const ax = a.execution_score ?? 0;
  const bx = b.execution_score ?? 0;
  if (bx !== ax) return bx - ax;
  return (b.setup_score ?? b.score) - (a.setup_score ?? a.score);
}

export default function DashboardPage() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["market-status"], queryFn: api.marketStatus, retry: 1, refetchInterval: 60_000 });
  const top = useQuery({
    queryKey: ["scanner-top", "inefficiency"],
    queryFn: () => api.scannerTop(0, "inefficiency"),
    retry: 1,
    refetchInterval: 60_000,
  });
  const run = useMutation({
    mutationFn: () => api.universeRun({ cheap_limit: 150, heavy_limit: 25, do_heavy: true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scanner-top"] });
      qc.invalidateQueries({ queryKey: ["market-status"] });
    },
  });

  const opportunities = [...(top.data?.smc_setups || [])].sort(rankOpportunity).slice(0, 9);

  const volRu: Record<string, string> = {
    high: "высокая",
    medium: "средняя",
    low: "низкая",
  };
  const trendRu: Record<string, string> = {
    bullish: "бычий",
    bearish: "медвежий",
    range: "флэт",
    neutral: "нейтральный",
  };

  return (
    <div className="space-y-8">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <motion.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="font-display text-4xl md:text-5xl tracking-tight"
          >
            Лучшие возможности
          </motion.h1>
          <p className="mt-3 max-w-2xl text-mist">
            Неэффективности рынка · Sweep + FVG + Order Block · сортировка Edge → Execution → Setup.
            Мажоры только при редком сильном Edge. Не общий SMC-сканер топ-объёма.
          </p>
        </div>
        <button
          type="button"
          onClick={() => run.mutate()}
          disabled={run.isPending}
          className="rounded-md bg-accent px-4 py-2 text-ink font-medium disabled:opacity-50"
        >
          {run.isPending ? "Поиск неэффективностей…" : "Обновить фид"}
        </button>
      </section>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          [
            "Тренд BTC",
            status.isLoading
              ? "…"
              : trendRu[String(status.data?.btc_trend || "").toLowerCase()] ||
                status.data?.btc_trend ||
                "—",
          ],
          [
            "Волатильность",
            status.isLoading
              ? "…"
              : volRu[String(status.data?.volatility || "").toLowerCase()] ||
                status.data?.volatility ||
                "—",
          ],
          ["В фиде", status.isLoading ? "…" : String(opportunities.length || top.data?.smc_setups?.length || 0)],
          ["Всплески объёма", status.isLoading ? "…" : String(status.data?.volume_spike_count ?? 0)],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-line bg-panel/50 px-4 py-3">
            <div className="text-xs uppercase tracking-wider text-mist">{label}</div>
            <div className="mt-1 font-display text-xl capitalize">{value}</div>
          </div>
        ))}
      </section>

      {run.isError && (
        <div className="rounded-lg border border-warn/40 bg-warn/10 p-4 text-sm space-y-2">
          <p className="font-medium">Сканер не запустился</p>
          <p className="text-mist">Проверьте, что API доступен.</p>
        </div>
      )}
      {run.isSuccess && (
        <div className="rounded-lg border border-accent/30 bg-accent/10 p-4 text-sm text-mist">
          L1: {String((run.data as { levels?: Record<string, number> })?.levels?.l1_universe ?? "—")} пар ·
          L2: {String((run.data as { levels?: Record<string, number> })?.levels?.l2_cheap ?? "—")} ·
          L3: {String((run.data as { levels?: Record<string, number> })?.levels?.l3_heavy ?? "—")} ·
          идей: {String((run.data as { levels?: Record<string, number> })?.levels?.trade_ideas ?? "—")}
        </div>
      )}

      <section>
        <h2 className="font-display text-2xl mb-4">Сильный Edge</h2>
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
          {opportunities.map((s) => (
            <SignalCard
              key={`${s.signal_type}-${s.id}`}
              signal={s}
              onRefresh={() => {
                qc.invalidateQueries({ queryKey: ["scanner-top"] });
              }}
            />
          ))}
          {!top.isLoading && opportunities.length === 0 && !top.isError && (
            <p className="text-mist col-span-full">
              Пока нет сетапов с подтверждённой структурой (Sweep+FVG+OB) и достаточным Edge.
              Нажмите «Обновить фид» или откройте сканер → «Все сигналы».
            </p>
          )}
        </div>
      </section>
    </div>
  );
}
