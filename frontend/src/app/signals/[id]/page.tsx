"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { api } from "@/services/api";
import { PriceChart } from "@/components/charts/PriceChart";
import { SignalCard } from "@/components/cards/SignalCard";

export default function SignalDetailsPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const [mode, setMode] = useState<"explain" | "plan" | "similar">("explain");

  const signal = useQuery({
    queryKey: ["signal", id],
    queryFn: () => api.signal(id),
    enabled: Number.isFinite(id),
  });

  const chart = useQuery({
    queryKey: ["chart", signal.data?.symbol, signal.data?.timeframe],
    queryFn: () => api.charts(signal.data!.symbol, signal.data!.timeframe || "15"),
    enabled: !!signal.data?.symbol,
  });

  const ai = useMutation({
    mutationFn: (m: "explain" | "plan" | "similar") => api.aiExplain(id, m),
  });

  const feedback = useMutation({
    mutationFn: (vote: "up" | "down" | "skip") => api.feedback(id, vote),
  });

  const zones = useMemo(() => {
    const z = signal.data?.zones || {};
    const list = [
      ...((z.fvg as Array<Record<string, unknown>>) || []),
      ...((z.order_blocks as Array<Record<string, unknown>>) || []),
      ...((z.liquidity_sweeps as Array<Record<string, unknown>>) || []),
    ];
    return list.map((item) => ({
      type: String(item.type || ""),
      top: item.top as number | undefined,
      bottom: item.bottom as number | undefined,
      price: item.price as number | undefined,
      direction: item.direction as string | undefined,
    }));
  }, [signal.data]);

  if (signal.isLoading) return <p className="text-mist">Загрузка сигнала…</p>;
  if (signal.isError || !signal.data) return <p className="text-danger">Сигнал не найден</p>;

  const s = signal.data;
  const aiData = ai.data as
    | {
        explanation?: string;
        summary?: string;
        confidence?: number;
        rating?: { final_assessment?: string; confidence?: number };
        similar?: { sample_size?: number; up_probability_pct?: number; average_rr?: number };
        source?: string;
      }
    | undefined;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs uppercase tracking-[0.2em] text-mist">Сигнал #{s.id}</p>
        <Link href={`/terminal?symbol=${s.symbol}`} className="text-sm text-accent">
          Открыть терминал
        </Link>
      </div>

      <div className="grid lg:grid-cols-[1.15fr_0.85fr] gap-6">
        <div className="space-y-4">
          <h2 className="font-display text-2xl">График</h2>
          <PriceChart candles={chart.data?.candles || []} zones={zones} />
        </div>
        <div className="space-y-4">
          <SignalCard signal={s} />

          <div className="rounded-xl border border-line bg-panel/60 p-5 space-y-3">
            <h3 className="font-display text-xl">AI Analysis</h3>
            <div className="flex flex-wrap gap-2">
              {(["explain", "plan", "similar"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => {
                    setMode(m);
                    ai.mutate(m);
                  }}
                  className="rounded-md border border-line px-3 py-1.5 text-sm hover:border-accent"
                >
                  {m}
                </button>
              ))}
            </div>
            {ai.isPending && <p className="text-sm text-mist">Собираю контекст…</p>}
            {aiData && (
              <div className="text-sm space-y-2">
                <p className="text-accent">{aiData.summary}</p>
                <p className="text-mist">
                  {aiData.rating?.final_assessment} · conf{" "}
                  {aiData.rating?.confidence ?? aiData.confidence} · source {aiData.source}
                </p>
                {mode === "similar" && aiData.similar && (
                  <p>
                    Similar n={aiData.similar.sample_size} · up{" "}
                    {aiData.similar.up_probability_pct}% · avg RR {aiData.similar.average_rr}
                  </p>
                )}
                <pre className="whitespace-pre-wrap font-sans text-slate-200">
                  {aiData.explanation || s.ai_comment || s.explanation}
                </pre>
              </div>
            )}
            {!aiData && (
              <pre className="whitespace-pre-wrap text-sm font-sans text-slate-200">
                {s.ai_comment || s.explanation || "Нажмите explain"}
              </pre>
            )}
            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={() => feedback.mutate("up")}
                className="text-sm px-2 py-1 border border-line rounded"
              >
                👍
              </button>
              <button
                type="button"
                onClick={() => feedback.mutate("down")}
                className="text-sm px-2 py-1 border border-line rounded"
              >
                👎
              </button>
              <button
                type="button"
                onClick={() => feedback.mutate("skip")}
                className="text-sm px-2 py-1 border border-line rounded"
              >
                ⏭
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
