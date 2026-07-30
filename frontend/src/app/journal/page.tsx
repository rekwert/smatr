"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/services/api";

export default function JournalPage() {
  const qc = useQueryClient();
  const stats = useQuery({ queryKey: ["journal-stats"], queryFn: api.journalStats, retry: 1 });
  const rows = useQuery({ queryKey: ["journal"], queryFn: () => api.journalList(40), retry: 1 });

  const [form, setForm] = useState({
    symbol: "",
    direction: "LONG",
    entry_price: "",
    exit_price: "",
    result: "win",
    result_r: "",
    notes: "",
    inefficiency_type: "sweep_reclaim",
  });

  const create = useMutation({
    mutationFn: () =>
      api.journalCreate({
        symbol: form.symbol.trim().toUpperCase(),
        direction: form.direction,
        entry_price: form.entry_price ? Number(form.entry_price) : null,
        exit_price: form.exit_price ? Number(form.exit_price) : null,
        result: form.result,
        result_r: form.result_r ? Number(form.result_r) : null,
        notes: form.notes || null,
        inefficiency_type: form.inefficiency_type,
        setup: "inefficiency",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["journal"] });
      qc.invalidateQueries({ queryKey: ["journal-stats"] });
      setForm((f) => ({ ...f, symbol: "", entry_price: "", exit_price: "", result_r: "", notes: "" }));
    },
  });

  const s = stats.data;

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="font-display text-4xl">Журнал неэффективностей</h1>
        <p className="text-mist mt-2">
          Ручные сделки по playbook. После 5+ закрытых Edge начинает учитывать реальный WinRate.
        </p>
      </div>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          ["WinRate", s?.winrate != null ? `${s.winrate}%` : "—"],
          ["Закрыто", String(s?.closed ?? "—")],
          ["Avg R", s?.avg_r != null ? `${s.avg_r}R` : "—"],
          ["Для Edge", s?.usable_for_edge ? "да" : "нужно ≥5"],
        ].map(([label, value]) => (
          <div key={label} className="rounded-lg border border-line bg-panel/50 px-4 py-3">
            <div className="text-xs uppercase tracking-wider text-mist">{label}</div>
            <div className="mt-1 font-display text-xl">{value}</div>
          </div>
        ))}
      </section>

      <section className="rounded-xl border border-line bg-panel/50 p-4 space-y-3">
        <h2 className="font-display text-xl">Добавить сделку</h2>
        <div className="grid md:grid-cols-3 gap-3 text-sm">
          <label className="space-y-1">
            <span className="text-mist">Символ</span>
            <input
              className="w-full rounded-md border border-line bg-ink/40 px-3 py-2"
              value={form.symbol}
              onChange={(e) => setForm({ ...form, symbol: e.target.value })}
              placeholder="WIFUSDT"
            />
          </label>
          <label className="space-y-1">
            <span className="text-mist">Направление</span>
            <select
              className="w-full rounded-md border border-line bg-ink/40 px-3 py-2"
              value={form.direction}
              onChange={(e) => setForm({ ...form, direction: e.target.value })}
            >
              <option value="LONG">LONG</option>
              <option value="SHORT">SHORT</option>
            </select>
          </label>
          <label className="space-y-1">
            <span className="text-mist">Результат</span>
            <select
              className="w-full rounded-md border border-line bg-ink/40 px-3 py-2"
              value={form.result}
              onChange={(e) => setForm({ ...form, result: e.target.value })}
            >
              <option value="win">win</option>
              <option value="loss">loss</option>
              <option value="be">be</option>
              <option value="open">open</option>
            </select>
          </label>
          <label className="space-y-1">
            <span className="text-mist">Entry</span>
            <input
              className="w-full rounded-md border border-line bg-ink/40 px-3 py-2"
              value={form.entry_price}
              onChange={(e) => setForm({ ...form, entry_price: e.target.value })}
            />
          </label>
          <label className="space-y-1">
            <span className="text-mist">Exit</span>
            <input
              className="w-full rounded-md border border-line bg-ink/40 px-3 py-2"
              value={form.exit_price}
              onChange={(e) => setForm({ ...form, exit_price: e.target.value })}
            />
          </label>
          <label className="space-y-1">
            <span className="text-mist">R-multiple</span>
            <input
              className="w-full rounded-md border border-line bg-ink/40 px-3 py-2"
              value={form.result_r}
              onChange={(e) => setForm({ ...form, result_r: e.target.value })}
              placeholder="1.5"
            />
          </label>
          <label className="space-y-1 md:col-span-2">
            <span className="text-mist">Тип</span>
            <select
              className="w-full rounded-md border border-line bg-ink/40 px-3 py-2"
              value={form.inefficiency_type}
              onChange={(e) => setForm({ ...form, inefficiency_type: e.target.value })}
            >
              <option value="sweep_reclaim">Sweep → FVG → OB</option>
              <option value="flash_spike">Flash spike</option>
            </select>
          </label>
          <label className="space-y-1 md:col-span-3">
            <span className="text-mist">Заметки</span>
            <input
              className="w-full rounded-md border border-line bg-ink/40 px-3 py-2"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </label>
        </div>
        <button
          type="button"
          disabled={!form.symbol || create.isPending}
          onClick={() => create.mutate()}
          className="rounded-md bg-accent px-4 py-2 text-ink font-medium disabled:opacity-50"
        >
          {create.isPending ? "Сохранение…" : "Сохранить в журнал"}
        </button>
        {create.isError && <p className="text-sm text-rose-300">Ошибка сохранения</p>}
      </section>

      <section className="space-y-3">
        <h2 className="font-display text-xl">Записи</h2>
        {(rows.data || []).map((t) => (
          <div key={t.id} className="rounded-lg border border-line bg-panel/40 px-4 py-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div className="font-display text-xl">
                {t.symbol}{" "}
                <span className="text-base text-mist">{t.side}</span>
              </div>
              <div
                className={
                  t.result === "win"
                    ? "text-emerald-300"
                    : t.result === "loss"
                      ? "text-rose-300"
                      : "text-mist"
                }
              >
                {t.result}
                {t.pnl != null ? ` · ${t.pnl}R` : ""}
              </div>
            </div>
            <p className="text-xs text-mist mt-1">
              {(t.meta as { inefficiency_type?: string })?.inefficiency_type || "inefficiency"}
              {t.entry_price != null ? ` · entry ${t.entry_price}` : ""}
              {t.exit_price != null ? ` → ${t.exit_price}` : ""}
            </p>
            {(t.meta as { notes?: string })?.notes && (
              <p className="text-sm mt-2">{(t.meta as { notes?: string }).notes}</p>
            )}
          </div>
        ))}
        {!rows.isLoading && !(rows.data || []).length && (
          <p className="text-mist">Пока пусто — добавьте первую сделку после playbook ENTRY READY.</p>
        )}
      </section>
    </div>
  );
}
