"use client";

const TYPES = [
  { icon: "🔥", title: "Ранний памп", desc: "Pump Score > 85, накопление и всплеск объёма" },
  { icon: "💧", title: "Снятие ликвидности", desc: "Liquidity Sweep / stop hunt" },
  { icon: "📈", title: "Пробой структуры", desc: "Подтверждённый BOS / CHoCH" },
  { icon: "🐋", title: "Крупный участник", desc: "Аномальные сделки / объём" },
  { icon: "⚠", title: "Риск", desc: "Инвалидация структуры или превышение риска" },
];

export default function AlertsPage() {
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="font-display text-4xl">Центр алертов</h1>
        <p className="text-mist mt-2">
          Уведомления в Telegram и на сайте. Антиспам: одна монета — не чаще раза за 30 минут.
        </p>
      </div>
      <div className="grid gap-3">
        {TYPES.map((t) => (
          <div key={t.title} className="rounded-xl border border-line bg-panel/50 px-5 py-4 flex gap-4">
            <span className="text-2xl">{t.icon}</span>
            <div>
              <div className="font-display text-lg">{t.title}</div>
              <p className="text-sm text-mist mt-1">{t.desc}</p>
            </div>
          </div>
        ))}
      </div>
      <p className="text-sm text-mist">
        Настройте минимальный score и каналы на странице «Настройки». История алертов хранится в
        PostgreSQL (`notifications`).
      </p>
    </div>
  );
}
