"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, type FeedMode } from "@/services/api";
import { useSettingsStore } from "@/stores/settingsStore";

export default function ScannerPage() {
  const { filters, setFilters } = useSettingsStore();
  const [debouncedScore, setDebouncedScore] = useState(filters.minScore);
  const qc = useQueryClient();
  const feed: FeedMode = filters.feed;

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedScore(filters.minScore), 250);
    return () => window.clearTimeout(t);
  }, [filters.minScore]);

  const signals = useQuery({
    queryKey: ["signals", debouncedScore, feed],
    queryFn: () => api.signals(debouncedScore, feed),
    retry: 1,
  });
  const run = useMutation({
    mutationFn: () =>
      feed === "inefficiency"
        ? api.runScan(20, "all")
        : api.runScan(20, "bybit"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["signals"] }),
  });

  const rows = (signals.data || []).filter((s) => {
    if (feed === "inefficiency" && s.signal_type === "pump") return false;
    if (!filters.smc && s.signal_type === "smc") return false;
    if (!filters.pump && s.signal_type === "pump") return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl">Сканер рынка</h1>
          <p className="text-mist mt-2">
            {feed === "inefficiency"
              ? "Неэффективности · Sweep+FVG+OB · Edge → Execution → Setup"
              : "Все сигналы · без гейта структуры (включая volume scan)"}
          </p>
        </div>
        <button
          onClick={() => run.mutate()}
          disabled={run.isPending}
          className="rounded-md bg-accent px-4 py-2 text-ink font-medium hover:opacity-90 disabled:opacity-50"
        >
          {run.isPending
            ? "Сканирование…"
            : feed === "inefficiency"
              ? "Обновить неэффективности"
              : "Volume scan (Bybit)"}
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {(
          [
            ["inefficiency", "Неэффективности"],
            ["all", "Все сигналы"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setFilters({ feed: id })}
            className={`rounded-md px-3 py-1.5 text-sm border ${
              feed === id
                ? "border-accent bg-accent/15 text-white"
                : "border-line bg-panel/40 text-mist hover:text-white"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-4 items-center rounded-xl border border-line bg-panel/50 p-4">
        <label className="text-sm flex items-center gap-2">
          <input
            type="checkbox"
            checked={filters.smc}
            onChange={(e) => setFilters({ smc: e.target.checked })}
          />
          SMC-сетапы
        </label>
        {feed !== "inefficiency" && (
          <label className="text-sm flex items-center gap-2">
            <input
              type="checkbox"
              checked={filters.pump}
              onChange={(e) => setFilters({ pump: e.target.checked })}
            />
            Детектор пампа
          </label>
        )}
        <label className="text-sm flex items-center gap-2">
          Score ≥ {filters.minScore}
          <input
            type="range"
            min={0}
            max={100}
            value={filters.minScore}
            onChange={(e) => setFilters({ minScore: Number(e.target.value) })}
          />
        </label>
      </div>

      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full text-sm">
          <thead className="bg-panel text-mist text-left">
            <tr>
              <th className="p-3">Символ</th>
              <th className="p-3">Биржа</th>
              <th className="p-3">Edge</th>
              <th className="p-3">Exec</th>
              <th className="p-3">Setup</th>
              <th className="p-3">Сторона</th>
              <th className="p-3">Тип</th>
              <th className="p-3">ТФ</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={`${s.exchange || "bybit"}-${s.id}`} className="border-t border-line/70 hover:bg-white/5">
                <td className="p-3">
                  <Link className="text-accent hover:underline" href={`/signals/${s.id}`}>
                    {s.symbol}
                  </Link>
                </td>
                <td className="p-3 capitalize text-mist">{s.exchange || "bybit"}</td>
                <td className="p-3 font-display text-lg">{s.edge_score ?? "—"}</td>
                <td className="p-3">{s.execution_score ?? "—"}</td>
                <td className="p-3">{s.setup_score ?? s.score}</td>
                <td className="p-3">{s.direction}</td>
                <td className="p-3 capitalize">{s.signal_type}</td>
                <td className="p-3">{s.timeframe}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <p className="p-6 text-mist">
            {feed === "inefficiency"
              ? "Нет строк с Sweep+FVG+OB и достаточным Edge. Переключитесь на «Все сигналы» или обновите фид."
              : "Нет строк. Запустите volume scan или снизьте порог score."}
          </p>
        )}
      </div>
    </div>
  );
}
