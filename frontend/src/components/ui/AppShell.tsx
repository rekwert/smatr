"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const links = [
  { href: "/dashboard", label: "Дашборд" },
  { href: "/scanner", label: "Сканер" },
  { href: "/hunter", label: "Hunter" },
  { href: "/terminal", label: "Терминал" },
  { href: "/positions", label: "Позиции" },
  { href: "/journal", label: "Журнал" },
  { href: "/assistant", label: "AI" },
  { href: "/alerts", label: "Алерты" },
  { href: "/exchanges", label: "Биржи" },
  { href: "/backtest", label: "Бэктест" },
  { href: "/replay", label: "Replay" },
  { href: "/settings", label: "Настройки" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen">
      <header className="border-b border-line/80 backdrop-blur sticky top-0 z-40 bg-ink/80">
        <div className="mx-auto max-w-7xl px-4 py-4 flex items-end justify-between gap-6">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-mist">Bybit · Linear USDT</p>
            <Link href="/dashboard" className="font-display text-2xl md:text-3xl tracking-tight">
              Smart Money AI Scanner
            </Link>
          </div>
          <nav className="flex flex-wrap gap-1.5 text-sm max-w-3xl justify-end">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={clsx(
                  "px-2.5 py-1.5 rounded-md transition",
                  pathname?.startsWith(l.href)
                    ? "bg-accent/20 text-accent"
                    : "text-mist hover:text-white hover:bg-white/5"
                )}
              >
                {l.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-8">{children}</main>
      <footer className="mx-auto max-w-7xl px-4 pb-10 text-xs text-mist/80">
        Только аналитический инструмент. Не финансовый совет. Автоторговля в MVP отключена.
        Прошлые паттерны не гарантируют будущий результат.
      </footer>
    </div>
  );
}
