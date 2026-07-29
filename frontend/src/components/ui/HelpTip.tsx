"use client";

import { useEffect, useId, useRef, useState } from "react";

/** Compact educational "?" tip for Signal Card learning mode. */
export function HelpTip({
  title,
  children,
  className = "",
}: {
  title?: string;
  children: React.ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <span ref={ref} className={`relative inline-flex align-middle ${className}`}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        aria-label={title || "Пояснение"}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-line/80 text-[10px] text-mist hover:text-slate-100 hover:border-accent/50"
      >
        ?
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          className="absolute z-30 left-0 top-5 w-64 rounded-lg border border-line bg-ink px-3 py-2 text-[11px] leading-relaxed text-slate-200 shadow-xl"
        >
          {title && <span className="block font-medium text-slate-100 mb-1">{title}</span>}
          <span className="text-mist">{children}</span>
        </span>
      )}
    </span>
  );
}

export const CARD_HELP = {
  timingLate:
    "Timing = Late значит цена уже ушла от Ideal Entry. Для SHORT это обычно Discount: шортить «вдогонку» рискованно — лучше ждать откат в Premium.",
  discountShort:
    "Discount — нижняя часть диапазона. Там цена уже дешёвая; новый SHORT хуже, потому что потенциал вниз меньше, а риск отскока вверх выше.",
  orderFlow:
    "Order Flow (дельта / агрессия продавцов) подтверждает, что крупные участники продают. Без него Structure может быть красивым, но вход «сейчас» слабый.",
  scenarioProb:
    "Вероятность сценария — насколько идея в целом ещё жива (Structure + контекст). Это не сигнал «входи прямо сейчас».",
  entryProbNow:
    "Вероятность входа сейчас — готовы ли фильтры исполнения у Ideal Entry. При Late почти всегда низкая.",
  chasing:
    "Chasing Risk — риск догона уже ушедшего движения. При Timing Late почти всегда HIGH: лучше WAIT RETEST, чем вход по рынку.",
  smartMoney:
    "Smart Money Activity — proxy участия крупных игроков: Accumulation / Distribution / Inactive по Sweep, BOS, OB, объёму и OI.",
  invalidation:
    "Invalidation — когда идея ломается. Для SHORT стоп и инвалидация должны быть ВЫШЕ Ideal Entry (закрепление выше Stop / swing high).",
  tradePlan:
    "План строится от Ideal Entry, не от текущей цены. SHORT: Stop выше Entry, TP ниже. LONG: Stop ниже Entry, TP выше.",
  edge:
    "Edge Score — эвристика «почему идея интереснее других»: ликвидность, OI, Sweep, зона, RR. «Оценка по сетапу» — не журнальный WinRate.",
  replay:
    "Replay — история смены статусов сценария (WATCH → ENTRY READY → TP1 / INVALIDATED). Помогает понять, где логика работает.",
  sweep:
    "Liquidity Sweep — сняли ликвидность за равными хаями/лоу? Это главный триггер идеи, важнее BOS.",
  fvg:
    "FVG / Imbalance — остался дисбаланс после импульса? Цена часто возвращается заполнять его.",
  orderBlock:
    "Order Block — зона, где вероятно заходил крупный участник. Точка интереса для ретеста.",
  bosMinor:
    "BOS — лишь подтверждение. Тезис строится на Sweep + FVG/OB + OI/Delta, а не на пробое структуры.",
} as const;
