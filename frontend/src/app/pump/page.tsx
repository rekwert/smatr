"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/services/api";

export default function PumpPage() {
  const top = useQuery({
    queryKey: ["pump-top"],
    queryFn: () => api.scannerTop(60),
  });
  const rows = top.data?.pump_candidates || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-4xl">Детектор пампа</h1>
        <p className="text-mist mt-2">
          Ранняя стадия: сжатие → накопление → объём → пробой → OI.
        </p>
      </div>

      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full text-sm">
          <thead className="bg-panel text-mist text-left">
            <tr>
              <th className="p-3">Токен</th>
              <th className="p-3">Pump Score</th>
              <th className="p-3">Причины</th>
              <th className="p-3">Статус</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id} className="border-t border-line/70">
                <td className="p-3">
                  <Link href={`/signals/${s.id}`} className="text-accent">
                    {s.symbol}
                  </Link>
                </td>
                <td className="p-3 font-display text-lg">{s.score}</td>
                <td className="p-3">{(s.reason?.found || []).slice(0, 3).join(" · ") || "—"}</td>
                <td className="p-3 capitalize">{s.reason?.pump?.status || s.confidence}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <p className="p-6 text-mist">Нет pump-кандидатов. Запустите scan.</p>}
      </div>
    </div>
  );
}
