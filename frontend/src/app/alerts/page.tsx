"use client";

const TYPES = [
  {
    icon: "🟢",
    title: "Неэффективность · ENTRY READY",
    desc: "Playbook зелёный: зона + RV≥2× + поток. Уходит в Telegram сразу (антиспам 45 мин на монету).",
  },
  { icon: "💧", title: "Sweep reclaim", desc: "Снятие ликвидности → FVG/OB → reclaim" },
  { icon: "⚡", title: "Flash spike", desc: "Тонкий импульс и возврат к базе (mean reversion)" },
  { icon: "📊", title: "Журнал → Edge", desc: "После 5+ закрытых сделок WinRate влияет на Edge Score" },
  { icon: "⚠", title: "Инвалидация / expiry", desc: "Событие сломано или окно истекло — в фид не попадает" },
];

export default function AlertsPage() {
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="font-display text-4xl">Центр алертов</h1>
        <p className="text-mist mt-2">
          Основной канал: Telegram при статусе «Можно искать вход». Нужны TELEGRAM_BOT_TOKEN и
          TELEGRAM_CHAT_ID в docker/.env.vps.
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
    </div>
  );
}
