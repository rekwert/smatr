"use client";

export default function JournalPage() {
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="font-display text-4xl">AI-журнал сделок</h1>
        <p className="text-mist mt-2">
          После закрытия сделки система сохраняет разбор: сетап, прогноз AI, факт и уроки.
        </p>
      </div>
      <div className="rounded-xl border border-line bg-panel/50 p-6 space-y-4">
        <p className="text-sm text-mist">
          Пока журнал пуст — сделки в MVP не исполняются автоматически. После первых ручных
          записей здесь появятся карточки вида:
        </p>
        <div className="rounded-lg border border-line/80 p-4">
          <div className="font-display text-xl">XYZUSDT</div>
          <p className="text-sm text-mist mt-1">Результат: +4.5R · Сетап: Liquidity Sweep</p>
          <p className="text-sm mt-3">Прогноз AI: 88% · Факт: успешный</p>
          <ul className="mt-3 text-sm space-y-1 text-slate-200">
            <li>✔ Вход был оптимальным</li>
            <li>✔ Дождаться ретеста FVG</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
