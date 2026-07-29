"use client";

import { useSettingsStore } from "@/stores/settingsStore";
import { RiskMeter } from "@/components/ui/ScoreRing";

const MODES = [
  { id: "scanner", label: "Сканер", desc: "Только поиск и алерты" },
  { id: "assisted", label: "С сопровождением", desc: "Планы + подтверждение вручную (MVP)" },
  { id: "auto", label: "Автоторговля", desc: "Отключено до PRO / бэктеста" },
] as const;

export default function SettingsPage() {
  const { filters, setFilters, tradingMode, setTradingMode } = useSettingsStore();

  return (
    <div className="space-y-6 max-w-xl">
      <div>
        <h1 className="font-display text-4xl">Настройки</h1>
        <p className="text-mist mt-2">Аккаунт, риск, уведомления и режим торговли.</p>
      </div>

      <div className="rounded-xl border border-line bg-panel/50 p-5 space-y-5">
        <div>
          <h2 className="font-display text-xl mb-3">Режим торговли</h2>
          <div className="space-y-2">
            {MODES.map((m) => (
              <label
                key={m.id}
                className="flex items-start gap-3 rounded-lg border border-line/80 px-3 py-2 cursor-pointer hover:bg-white/5"
              >
                <input
                  type="radio"
                  name="mode"
                  checked={tradingMode === m.id}
                  disabled={m.id === "auto"}
                  onChange={() => setTradingMode(m.id)}
                  className="mt-1"
                />
                <span>
                  <span className="block font-medium">{m.label}</span>
                  <span className="text-sm text-mist">{m.desc}</span>
                </span>
              </label>
            ))}
          </div>
        </div>

        <label className="block text-sm">
          Минимальный score: {filters.minScore}
          <input
            type="range"
            min={0}
            max={100}
            value={filters.minScore}
            onChange={(e) => setFilters({ minScore: Number(e.target.value) })}
            className="w-full mt-2"
          />
        </label>

        <RiskMeter level="medium" />

        <div className="text-sm text-mist space-y-1">
          <p>Риск на сделку по умолчанию: 1%</p>
          <p>Минимальный RR: 2.5</p>
          <p>Telegram: токен и chat_id в переменных окружения backend</p>
        </div>
      </div>
    </div>
  );
}
