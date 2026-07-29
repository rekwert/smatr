"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/services/api";

export default function PositionsPage() {
  const signals = useQuery({
    queryKey: ["positions-signals"],
    queryFn: () => api.signals(70),
    retry: 1,
  });

  const rows = (signals.data || []).filter((s) => s.status === "active").slice(0, 20);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-4xl">Позиции</h1>
        <p className="text-mist mt-2">
          MVP: открытые сделки пока не исполняются на бирже. Здесь — активные сценарии для
          ручного подтверждения.
        </p>
      </div>
      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full text-sm">
          <thead className="bg-panel/80 text-mist text-left">
            <tr>
              <th className="px-4 py-3">Символ</th>
              <th className="px-4 py-3">Сторона</th>
              <th className="px-4 py-3">Вход</th>
              <th className="px-4 py-3">Стоп</th>
              <th className="px-4 py-3">Цель</th>
              <th className="px-4 py-3">Score</th>
              <th className="px-4 py-3">Статус</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id} className="border-t border-line/60 hover:bg-white/5">
                <td className="px-4 py-3">
                  <Link href={`/terminal?symbol=${s.symbol}`} className="text-accent hover:underline">
                    {s.symbol}
                  </Link>
                </td>
                <td className="px-4 py-3">{s.direction}</td>
                <td className="px-4 py-3">{s.entry ?? "—"}</td>
                <td className="px-4 py-3">{s.stop ?? "—"}</td>
                <td className="px-4 py-3">{s.target ?? "—"}</td>
                <td className="px-4 py-3">{s.score}</td>
                <td className="px-4 py-3 text-accent">Наблюдение</td>
              </tr>
            ))}
            {!signals.isLoading && rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-mist text-center">
                  Нет активных сценариев. Запустите сканер.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
