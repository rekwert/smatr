"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/services/api";

export default function BacktestPage() {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [strategy, setStrategy] = useState("smc");
  const [entryModel, setEntryModel] = useState("aggressive");
  const [minScore, setMinScore] = useState(75);

  const run = useMutation({
    mutationFn: () =>
      api.backtest({
        strategy,
        symbol,
        timeframe: "15",
        period: "recent",
        risk_pct: 1,
        limit: 500,
        min_score: minScore,
        entry_model: entryModel,
      }),
  });

  const result = run.data as
    | {
        trades?: number;
        winrate?: number;
        profit_factor?: number;
        drawdown?: number;
        metrics?: {
          metrics?: {
            average_rr?: number;
            expectancy?: number;
            trades?: number;
          };
          equity_curve?: number[];
          disclaimer?: string;
          candles_used?: number;
        };
      }
    | undefined;

  const m = result?.metrics?.metrics || {};

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="font-display text-4xl">Исследование стратегий</h1>
        <p className="text-mist mt-2">
          Исторический replay SMC/Pump на Bybit + симулятор сделок с комиссиями.
        </p>
      </div>
      <div className="rounded-xl border border-line bg-panel/50 p-5 space-y-4">
        <label className="block text-sm">
          Символ
          <input
            className="mt-1 w-full rounded-md bg-ink border border-line px-3 py-2"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          />
        </label>
        <label className="block text-sm">
          Стратегия
          <select
            className="mt-1 w-full rounded-md bg-ink border border-line px-3 py-2"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
          >
            <option value="smc">SMC</option>
            <option value="sweep_fvg">Sweep + FVG</option>
            <option value="pump">Pump</option>
          </select>
        </label>
        <label className="block text-sm">
          Модель входа
          <select
            className="mt-1 w-full rounded-md bg-ink border border-line px-3 py-2"
            value={entryModel}
            onChange={(e) => setEntryModel(e.target.value)}
          >
            <option value="aggressive">Агрессивный</option>
            <option value="conservative">Консервативный</option>
            <option value="limit">Лимитный</option>
          </select>
        </label>
        <label className="block text-sm">
          Мин. score: {minScore}
          <input
            type="range"
            min={50}
            max={95}
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="w-full mt-2"
          />
        </label>
        <button
          onClick={() => run.mutate()}
          disabled={run.isPending}
          className="rounded-md bg-accent px-4 py-2 text-ink font-medium disabled:opacity-50"
        >
          {run.isPending ? "Считаем…" : "Запустить бэктест"}
        </button>
      </div>
      {result && (
        <div className="grid grid-cols-2 gap-3">
          {[
            ["Сделки", result.trades ?? m.trades],
            ["Win Rate", `${result.winrate ?? 0}%`],
            ["Profit Factor", result.profit_factor],
            ["Макс. DD (R)", result.drawdown],
            ["Средний RR", m.average_rr],
            ["Expectancy", m.expectancy],
            ["Sharpe (R)", (m as { sharpe?: number }).sharpe],
          ].map(([k, v]) => (
            <div key={String(k)} className="rounded-lg border border-line bg-panel/50 p-4">
              <div className="text-xs text-mist uppercase tracking-wider">{k}</div>
              <div className="font-display text-2xl mt-1">{String(v ?? "—")}</div>
            </div>
          ))}
          <p className="col-span-2 text-xs text-mist">
            свечей={result.metrics?.candles_used} · {result.metrics?.disclaimer}
          </p>
          {!!result.metrics?.equity_curve?.length && (
            <p className="col-span-2 text-xs text-mist">
              Equity (R): {result.metrics.equity_curve.slice(-12).join(" → ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
