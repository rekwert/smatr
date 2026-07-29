"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";

export default function ExchangesPage() {
  const status = useQuery({ queryKey: ["ex-status"], queryFn: api.exchangeStatus, retry: 1 });
  const universe = useQuery({
    queryKey: ["ex-universe"],
    queryFn: () => api.exchangeUniverse(5_000_000),
    retry: 1,
  });
  const lowcap = useQuery({ queryKey: ["ex-lowcap"], queryFn: api.lowcap, retry: 1 });
  const listings = useQuery({ queryKey: ["ex-listings"], queryFn: api.newListings, retry: 1 });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-4xl">Статус бирж</h1>
        <p className="text-mist mt-2">
          Слой multi-exchange: Bybit, OKX, Bitget, MEXC, BingX, KuCoin — единый формат → SMC / Pump /
          AI.
        </p>
      </div>

      <section className="grid md:grid-cols-3 gap-3">
        {(status.data?.exchanges || []).map((ex) => (
          <div key={String(ex.exchange)} className="rounded-xl border border-line bg-panel/60 p-4">
            <div className="flex items-center justify-between">
              <span className="font-display text-xl capitalize">{String(ex.exchange)}</span>
              <span>{String(ex.emoji || "")}</span>
            </div>
            <p className="text-sm text-mist mt-2 uppercase">{String(ex.status)}</p>
            <p className="text-sm mt-1">Задержка: {String(ex.latency_ms ?? "—")} мс</p>
            {ex.error ? <p className="text-xs text-warn mt-2">{String(ex.error)}</p> : null}
          </div>
        ))}
        {status.isError && (
          <p className="text-warn col-span-full">Не удалось получить статус бирж (API offline?).</p>
        )}
      </section>

      <section>
        <h2 className="font-display text-2xl mb-3">Сканер низкой ликвидности</h2>
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full text-sm">
            <thead className="bg-panel text-mist text-left">
              <tr>
                <th className="p-3">Exchange</th>
                <th className="p-3">Symbol</th>
                <th className="p-3">Vol 24h</th>
                <th className="p-3">Liq</th>
                <th className="p-3">Pump hint</th>
              </tr>
            </thead>
            <tbody>
              {(lowcap.data?.candidates || []).slice(0, 15).map((r) => (
                <tr key={`${r.exchange}-${r.symbol}`} className="border-t border-line/70">
                  <td className="p-3 capitalize">{String(r.exchange)}</td>
                  <td className="p-3">{String(r.symbol)}</td>
                  <td className="p-3">{Number(r.volume24h || 0).toLocaleString()}</td>
                  <td className="p-3">{String(r.liquidity_score)}</td>
                  <td className="p-3 text-accent">{String(r.pump_hint_score)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="font-display text-2xl mb-3">New Futures Listings</h2>
        <div className="space-y-2">
          {(listings.data?.listings || []).slice(0, 10).map((r) => (
            <div
              key={`${r.exchange}-${r.symbol}-${r.listed_at}`}
              className="rounded-lg border border-line bg-panel/40 px-4 py-3 text-sm"
            >
              <span className="text-accent font-medium">{String(r.symbol)}</span> ·{" "}
              <span className="capitalize">{String(r.exchange)}</span> · age {String(r.age_hours)}h ·
              vol {Number(r.volume24h || 0).toLocaleString()}
            </div>
          ))}
          {!listings.data?.listings?.length && (
            <p className="text-mist text-sm">Нет свежих листингов в окне или биржа не отдала listTime.</p>
          )}
        </div>
      </section>

      <section>
        <h2 className="font-display text-2xl mb-3">Universe (top by liquidity)</h2>
        <p className="text-mist text-sm mb-2">Показано {universe.data?.count ?? 0} инструментов</p>
        <div className="overflow-x-auto rounded-xl border border-line max-h-80">
          <table className="w-full text-sm">
            <thead className="bg-panel text-mist text-left sticky top-0">
              <tr>
                <th className="p-3">Exchange</th>
                <th className="p-3">Symbol</th>
                <th className="p-3">Price</th>
                <th className="p-3">Liq score</th>
              </tr>
            </thead>
            <tbody>
              {(universe.data?.symbols || []).slice(0, 40).map((r) => (
                <tr key={`${r.exchange}-${r.symbol}-u`} className="border-t border-line/70">
                  <td className="p-3 capitalize">{String(r.exchange)}</td>
                  <td className="p-3">{String(r.symbol)}</td>
                  <td className="p-3">{String(r.price)}</td>
                  <td className="p-3">{String(r.liquidity_score)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
