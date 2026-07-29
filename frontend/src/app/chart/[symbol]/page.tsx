"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { api } from "@/services/api";
import { PriceChart } from "@/components/charts/PriceChart";

function ChartInner() {
  const params = useParams<{ symbol: string }>();
  const search = useSearchParams();
  const symbol = String(params.symbol || "").toUpperCase();
  const tf = search.get("tf") || "15";

  const chart = useQuery({
    queryKey: ["chart-ws", symbol, tf],
    queryFn: () => api.charts(symbol, tf),
    enabled: !!symbol,
  });

  const mtf = [
    { tf: "D", label: "Daily" },
    { tf: "240", label: "4H" },
    { tf: "60", label: "1H" },
    { tf: "15", label: "15M" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-mist">Chart Workspace</p>
        <h1 className="font-display text-4xl">{symbol}</h1>
      </div>

      <div className="grid md:grid-cols-4 gap-3">
        {mtf.map((m) => (
          <div key={m.tf} className="rounded-lg border border-line bg-panel/50 p-4">
            <div className="text-xs uppercase tracking-wider text-mist">{m.label}</div>
            <div className="mt-2 text-sm text-slate-200">
              {m.tf === tf ? "Active chart" : `TF ${m.tf}`}
            </div>
          </div>
        ))}
      </div>

      <PriceChart candles={chart.data?.candles || []} />
    </div>
  );
}

export default function ChartWorkspacePage() {
  return (
    <Suspense fallback={<p className="text-mist">Loading chart…</p>}>
      <ChartInner />
    </Suspense>
  );
}
