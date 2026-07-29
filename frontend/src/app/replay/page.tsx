"use client";

import Link from "next/link";

export default function ReplayPage() {
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="font-display text-4xl">Market Replay</h1>
        <p className="text-mist mt-2">
          Машина времени для проверки сетапов без look-ahead bias. Полноценный UI (Play / Speed /
          Jump) — в развитии; сейчас доступен исследовательский бэктест.
        </p>
      </div>
      <div className="rounded-xl border border-line bg-panel/50 p-6 space-y-4">
        <p className="text-sm">
          Запустите исторический прогон SMC / Pump / Sweep+FVG на странице бэктеста: свечи → сигнал
          → план → симулятор с комиссиями и проскальзыванием.
        </p>
        <Link
          href="/backtest"
          className="inline-block rounded-md bg-accent/90 px-4 py-2 text-ink font-medium hover:bg-accent"
        >
          Открыть бэктест
        </Link>
      </div>
    </div>
  );
}
