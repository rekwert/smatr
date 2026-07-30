"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect } from "react";
import { api } from "@/services/api";

export default function HunterPage() {
  const run = useMutation({
    mutationFn: () => api.pumpHunter(20),
  });

  // Auto-scan on open — Hunter previously looked "broken" because it never ran
  useEffect(() => {
    run.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rows = (run.data?.candidates || []) as Array<Record<string, unknown>>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl">Low Cap Hunter</h1>
          <p className="text-mist mt-2 max-w-2xl">
            Ищем mid/low liquidity <em>до</em> расширения: накопление → сжатие → объём → структура.
            Диапазон оборота ~0.5–25M USDT · порог score ≥50.
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

      {run.data?.disclaimer && (
        <p className="text-xs text-mist">{String(run.data.disclaimer)}</p>
      )}
      {run.isError && (
        <div className="rounded-lg border border-warn/40 bg-warn/10 p-4 text-sm">
          Скан не удался. Проверьте API и сеть, затем нажмите «Запустить Hunter» ещё раз.
        </div>
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
            <p className="text-xs text-mist mt-3">Quality {String(r.quality)}</p>
          </div>
        ))}
      </div>

      {run.isPending && (
        <p className="text-mist">Сканируем mid/low liquidity на 6 биржах (~30–90 с)…</p>
      )}
      {!rows.length && !run.isPending && !run.isError && (
        <p className="text-mist">
          Кандидатов нет в текущем окне рынка. Нажмите «Запустить Hunter» ещё раз позже.
        </p>
      )}
    </div>
  );
}
