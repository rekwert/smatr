"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/services/api";

export default function HunterPage() {
  const q = useQuery({
    queryKey: ["pump-hunter"],
    queryFn: () => api.pumpHunter(12),
    retry: 0,
    enabled: false,
  });
  const run = useMutation({
    mutationFn: () => api.pumpHunter(12),
  });

  const rows = (run.data?.candidates || q.data?.candidates || []) as Array<
    Record<string, unknown>
  >;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl">Low Cap Hunter</h1>
          <p className="text-mist mt-2 max-w-2xl">
            Ищем состояние <em>до</em> расширения: накопление → сжатие → объём → структура. Не
            догоняем уже выросшие +50%.
          </p>
        </div>
        <button
          onClick={() => run.mutate()}
          disabled={run.isPending}
          className="rounded-md bg-accent px-4 py-2 text-ink font-medium disabled:opacity-50"
        >
          {run.isPending ? "Сканирование бирж…" : "Запустить Hunter"}
        </button>
      </div>

      {(run.data?.disclaimer || q.data?.disclaimer) && (
        <p className="text-xs text-mist">{String(run.data?.disclaimer || q.data?.disclaimer)}</p>
      )}

      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {rows.map((r) => (
          <div key={`${r.exchange}-${r.symbol}`} className="rounded-xl border border-line bg-panel/70 p-5">
            <div className="flex justify-between gap-3">
              <div>
                <Link
                  href={`/terminal?symbol=${r.symbol}&exchange=${r.exchange}`}
                  className="font-display text-2xl text-accent hover:underline"
                >
                  {String(r.symbol)}
                </Link>
                <p className="text-sm text-mist capitalize mt-1">{String(r.exchange)}</p>
              </div>
              <div className="text-right">
                <div className="font-display text-3xl text-accent">{String(r.score)}</div>
                <div className="text-xs uppercase tracking-wider text-mist">{String(r.status)}</div>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
              {Object.entries((r.components as Record<string, number>) || {})
                .filter(([k]) =>
                  ["accumulation", "volume_growth", "whale_activity", "oi_growth", "structure"].includes(k)
                )
                .map(([k, v]) => (
                  <div key={k} className="rounded-md bg-ink/40 px-2 py-1">
                    <span className="text-mist text-xs">{k.replaceAll("_", " ")}</span>
                    <div>{v}</div>
                  </div>
                ))}
            </div>
            <ul className="mt-3 text-sm space-y-1">
              {((r.reasons as string[]) || []).slice(0, 4).map((x) => (
                <li key={x}>✓ {x}</li>
              ))}
            </ul>
            {!!((r.red_flags as string[]) || []).length && (
              <p className="mt-2 text-xs text-warn">{(r.red_flags as string[]).join(" · ")}</p>
            )}
            <p className="mt-3 text-xs text-mist">Quality {String(r.quality)}</p>
          </div>
        ))}
      </div>

      {!rows.length && !run.isPending && (
        <p className="text-mist">Нажмите «Запустить Hunter» — сканирование бирж (может занять ~30 с).</p>
      )}
    </div>
  );
}
