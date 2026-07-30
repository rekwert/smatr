"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import type { RangeScale, Signal } from "@/types";
import { CARD_HELP, HelpTip } from "@/components/ui/HelpTip";

const STATUS_STYLE: Record<string, string> = {
  IGNORE: "border-zinc-600 bg-zinc-800/40 text-zinc-300",
  WATCH: "border-amber-500/50 bg-amber-500/10 text-amber-100",
  SETUP_FORMING: "border-sky-500/50 bg-sky-500/10 text-sky-100",
  ENTRY_ZONE: "border-violet-500/50 bg-violet-500/10 text-violet-100",
  ENTRY_READY: "border-emerald-500/50 bg-emerald-500/10 text-emerald-100",
  IN_POSITION: "border-orange-500/50 bg-orange-500/10 text-orange-100",
  TP1_HIT: "border-emerald-500/40 bg-emerald-500/10 text-emerald-100",
  TP2_HIT: "border-emerald-500/40 bg-emerald-500/10 text-emerald-100",
  INVALIDATED: "border-rose-700/60 bg-rose-950/40 text-rose-200",
};

function fmt(n?: number | null): string {
  if (n == null || Number.isNaN(Number(n))) return "—";
  const v = Number(n);
  if (Math.abs(v) >= 100) return v.toFixed(2);
  if (Math.abs(v) >= 1) return v.toFixed(4);
  return v.toFixed(6);
}

function starsFromScore(score: number): string {
  const filled = Math.max(0, Math.min(5, Math.round(score / 20)));
  return "★".repeat(filled) + "☆".repeat(5 - filled);
}

function ageLabel(createdAt?: string | null, ageSec?: number | null): string {
  if (typeof ageSec === "number") {
    if (ageSec < 60) return `${ageSec} сек. назад`;
    if (ageSec < 3600) return `${Math.floor(ageSec / 60)} мин. назад`;
    return `${Math.floor(ageSec / 3600)} ч назад`;
  }
  if (!createdAt) return "—";
  const t = Date.parse(createdAt);
  if (!Number.isFinite(t)) return "—";
  const sec = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (sec < 60) return `${sec} сек. назад`;
  if (sec < 3600) return `${Math.floor(sec / 60)} мин. назад`;
  return `${Math.floor(sec / 3600)} ч назад`;
}

function Divider() {
  return <div className="border-t border-line/70" />;
}

function ProbBar({ value, tone }: { value: number; tone: "scenario" | "entry" }) {
  const pct = Math.max(0, Math.min(100, value));
  const fill =
    tone === "scenario"
      ? "bg-emerald-400/80"
      : pct < 25
        ? "bg-rose-400/80"
        : pct < 55
          ? "bg-amber-400/80"
          : "bg-sky-400/80";
  return (
    <div className="h-2 rounded bg-line overflow-hidden">
      <div className={`h-full ${fill}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function RiskBar({ value, level }: { value: number; level?: string | null }) {
  const pct = Math.max(0, Math.min(100, value));
  const fill =
    level === "HIGH" || pct >= 70
      ? "bg-rose-400/85"
      : level === "MEDIUM" || pct >= 40
        ? "bg-amber-400/85"
        : "bg-emerald-400/85";
  return (
    <div className="h-2 rounded bg-line overflow-hidden">
      <div className={`h-full ${fill}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function RangeLadder({ scale }: { scale?: RangeScale | null }) {
  if (!scale || scale.price_pct == null) {
    return (
      <div className="text-[11px] text-mist">Range: недостаточно данных</div>
    );
  }
  const priceY = 100 - scale.price_pct;
  const idealLo = scale.ideal_low_pct != null ? 100 - scale.ideal_low_pct : null;
  const idealHi = scale.ideal_high_pct != null ? 100 - scale.ideal_high_pct : null;
  const bandTop = idealHi != null && idealLo != null ? Math.min(idealHi, idealLo) : null;
  const bandH =
    idealHi != null && idealLo != null ? Math.abs(idealHi - idealLo) : null;

  return (
    <div className="space-y-2">
      <div className="text-[10px] uppercase tracking-wide text-mist">Range</div>
      <div className="relative h-36 rounded-lg overflow-hidden border border-line/60">
        <div
          className="absolute inset-x-0 top-0 h-1/2"
          style={{
            background: "linear-gradient(180deg, rgba(244,63,94,0.35), rgba(244,63,94,0.05))",
          }}
        />
        <div
          className="absolute inset-x-0 bottom-0 h-1/2"
          style={{
            background: "linear-gradient(0deg, rgba(16,185,129,0.35), rgba(16,185,129,0.05))",
          }}
        />
        {bandTop != null && bandH != null && (
          <div
            className="absolute inset-x-2 rounded border border-amber-300/50 bg-amber-400/15"
            style={{ top: `${bandTop}%`, height: `${Math.max(bandH, 2)}%` }}
            title="Ideal Entry"
          />
        )}
        <div
          className="absolute left-2 right-2 h-0.5 bg-slate-100 shadow"
          style={{ top: `${priceY}%` }}
        />
        <div
          className="absolute right-2 -translate-y-1/2 text-[10px] text-slate-100 bg-ink/70 px-1.5 py-0.5 rounded"
          style={{ top: `${priceY}%` }}
        >
          Price {fmt(scale.price)}
        </div>
        <div className="absolute left-2 top-1.5 text-[10px] text-rose-100/90">Premium</div>
        <div className="absolute left-2 bottom-1.5 text-[10px] text-emerald-100/90">Discount</div>
        {scale.ideal_mid != null && (
          <div className="absolute left-2 top-1/2 -translate-y-1/2 text-[10px] text-amber-100/90">
            Ideal {fmt(scale.ideal_mid)}
          </div>
        )}
      </div>
      <div className="flex justify-between text-[10px] text-mist tabular-nums">
        <span>Low {fmt(scale.low)}</span>
        <span>High {fmt(scale.high)}</span>
      </div>
    </div>
  );
}

export function SignalCard({
  signal,
  onRefresh,
}: {
  signal: Signal;
  onRefresh?: () => void;
}) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => {
      setTick((x) => x + 1);
      onRefresh?.();
    }, (signal.reeval_sec || 60) * 1000);
    return () => window.clearInterval(id);
  }, [onRefresh, signal.reeval_sec]);

  const setup = signal.setup_score ?? signal.score;
  const execution = signal.execution_score ?? 0;
  const setupStars = signal.setup_stars || starsFromScore(setup);
  const execStars = signal.execution_stars || starsFromScore(execution);
  const life = signal.lifecycle_status || "WATCH";
  const emoji = signal.lifecycle_emoji || "🟡";
  const dirEmoji = signal.direction === "SHORT" ? "🔴" : "🟢";
  const confirmed = signal.reason?.confirmed || signal.reason?.found || [];
  const waiting = signal.waiting_for || [];
  const action = signal.action;
  const tp1 = signal.tp1 ?? null;
  const idealLow = signal.ideal_entry_low;
  const idealHigh = signal.ideal_entry_high;
  const ideal = signal.ideal_entry ?? signal.entry;
  const lights = signal.traffic_lights || {};
  const breakdown = signal.execution_breakdown?.parts || {};
  const why = signal.why_no_entry;
  const drivers = signal.confidence_drivers || [];
  const invalidation = signal.invalidation || [];
  const nextTrigger = signal.next_trigger;
  const history = signal.score_history || [];
  const scenarioProb = signal.scenario_probability ?? signal.probability;
  const entryProb = signal.entry_probability_now;
  const createdMs = signal.created_at ? Date.parse(signal.created_at) : NaN;
  const liveAge = Number.isFinite(createdMs)
    ? Math.max(0, Math.floor((Date.now() - createdMs) / 1000))
    : signal.age_sec ?? 0;

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-line bg-panel/85 p-5 flex flex-col gap-3.5 hover:border-accent/30 transition"
    >
      <header className="flex items-start justify-between gap-3">
        <div>
          <Link href={`/signals/${signal.id}`} className="font-display text-2xl tracking-tight hover:text-accent">
            {signal.symbol}
            <span className="ml-2 text-base font-sans font-medium text-mist tracking-normal">
              {(signal.exchange || "bybit").replace(/^./, (c) => c.toUpperCase())}
            </span>
          </Link>
          <p className="mt-1 text-sm font-medium">
            {dirEmoji} {signal.direction}
          </p>
        </div>
        <div className={`rounded-lg border px-2.5 py-1.5 text-xs text-right ${STATUS_STYLE[life] || STATUS_STYLE.WATCH}`}>
          <div className="font-medium">
            {emoji} {life.replaceAll("_", " ")}
          </div>
          <div className="opacity-80 mt-0.5">{signal.lifecycle_ru || "Наблюдение"}</div>
        </div>
      </header>

      <Divider />

      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <div className="text-mist uppercase tracking-wide">Market Phase</div>
          <div className="mt-1 text-slate-100 font-medium">{signal.phase || "—"}</div>
        </div>
        <div>
          <div className="text-mist uppercase tracking-wide flex items-center">
            Timing
            <HelpTip title="Timing">{CARD_HELP.timingLate}</HelpTip>
          </div>
          <div className="mt-1 text-slate-100 font-medium">
            {signal.timing_emoji || "🟡"} {signal.timing || "—"}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 text-[11px]">
        {[
          ["Structure", lights.structure, null],
          ["Execution", lights.execution, null],
          ["Order Flow", lights.orderflow, CARD_HELP.orderFlow],
          ["Timing", lights.timing, CARD_HELP.timingLate],
          ["Risk", lights.risk, null],
        ].map(([k, v, tip]) => (
          <span key={String(k)} className="rounded border border-line/70 px-2 py-0.5 text-slate-200 inline-flex items-center">
            {k} {v || "🟡"}
            {tip ? <HelpTip title={String(k)}>{String(tip)}</HelpTip> : null}
          </span>
        ))}
      </div>

      <Divider />

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <div className="text-[10px] uppercase tracking-wide text-mist flex items-center">
            Structure
            <HelpTip title="Structure / Idea">{CARD_HELP.sweep}{" "}{CARD_HELP.bosMinor}</HelpTip>
          </div>
          <div className="font-display text-2xl text-accent mt-0.5">{setup}</div>
          <div className="text-amber-300/90 tracking-widest text-sm mt-0.5">{setupStars}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wide text-mist">Execution</div>
          <div className="font-display text-2xl text-sky-300 mt-0.5">{execution}</div>
          <div className="text-amber-300/90 tracking-widest text-sm mt-0.5">{execStars}</div>
        </div>
      </div>

      {(signal.edge_score != null || (signal.edge_reasons && signal.edge_reasons.length > 0)) && (
        <div className="rounded-lg border border-accent/30 bg-accent/5 px-3 py-2.5 space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <div className="text-[10px] uppercase tracking-wide text-mist flex items-center">
              Edge
              <HelpTip title="Edge Score">{CARD_HELP.edge}</HelpTip>
            </div>
            <div className="font-display text-2xl text-accent tabular-nums">{signal.edge_score ?? "—"}</div>
          </div>
          {signal.edge_stars && (
            <div className="text-amber-300/90 tracking-widest text-sm">{signal.edge_stars}</div>
          )}
          {(signal.inefficiency_type_ru || signal.inefficiency_thesis) && (
            <div className="rounded-md border border-line/50 bg-ink/30 px-2 py-1.5 space-y-0.5">
              <div className="text-[11px] text-slate-100 font-medium">
                {signal.inefficiency_type_ru || "Неэффективность"}
                {signal.inefficiency_strength != null ? (
                  <span className="text-mist font-normal"> · сила {signal.inefficiency_strength}</span>
                ) : null}
              </div>
              {signal.inefficiency_status_ru && (
                <p className="text-[11px] text-amber-100/90">
                  Статус: {signal.inefficiency_status_ru}
                </p>
              )}
              {signal.inefficiency_thesis && (
                <p className="text-[10px] text-mist leading-snug">{signal.inefficiency_thesis}</p>
              )}
              <div className="flex flex-wrap gap-2 text-[10px] text-mist pt-0.5">
                {signal.relative_volume != null && (
                  <span>RV×{Number(signal.relative_volume).toFixed(2)}</span>
                )}
                {signal.displacement_pct != null && Number(signal.displacement_pct) > 0 && (
                  <span>смещение {Number(signal.displacement_pct).toFixed(1)}%</span>
                )}
              </div>
            </div>
          )}
          {(signal.inefficiency_playbook || []).length > 0 && (
            <ul className="space-y-1 border border-line/40 rounded-md px-2 py-1.5 bg-ink/20">
              <li className="text-[10px] uppercase tracking-wide text-mist">Playbook</li>
              {(signal.inefficiency_playbook || []).map((step) => (
                <li key={String(step.key || step.label)} className="text-[11px] text-slate-200">
                  {step.done ? "✅" : "□"} {String(step.label || "")}
                </li>
              ))}
            </ul>
          )}
          <ul className="space-y-0.5">
            {(signal.edge_reasons || []).slice(0, 7).map((r) => (
              <li key={r} className="text-xs text-emerald-300/90">
                {r}
              </li>
            ))}
          </ul>
          {signal.edge_hint && <p className="text-[10px] text-mist">{signal.edge_hint}</p>}
          {(signal.entry_blockers || []).length > 0 && (
            <ul className="space-y-0.5 border-t border-line/40 pt-1.5">
              {(signal.entry_blockers || []).slice(0, 3).map((b) => (
                <li key={b} className="text-[10px] text-amber-200/90">
                  ⏳ {b}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="rounded-lg border border-line/60 bg-ink/25 p-3 space-y-3">
        <div className="space-y-1.5">
          <div className="flex items-end justify-between gap-2">
            <div className="text-[10px] uppercase tracking-wide text-mist flex items-center">
              Вероятность сценария
              <HelpTip title="Scenario Probability">{CARD_HELP.scenarioProb}</HelpTip>
            </div>
            <div className="font-display text-lg text-slate-100 tabular-nums">{scenarioProb ?? "—"}%</div>
          </div>
          <ProbBar value={Number(scenarioProb ?? 0)} tone="scenario" />
          <p className="text-[11px] text-mist leading-snug">
            Вероятность того, что сценарий вообще реализуется.
          </p>
        </div>
        <div className="space-y-1.5 border-t border-line/50 pt-3">
          <div className="flex items-end justify-between gap-2">
            <div className="text-[10px] uppercase tracking-wide text-mist flex items-center">
              Вероятность входа СЕЙЧАС
              <HelpTip title="Entry Now">{CARD_HELP.entryProbNow}</HelpTip>
            </div>
            <div className="font-display text-lg text-slate-100 tabular-nums">{entryProb ?? "—"}%</div>
          </div>
          <ProbBar value={Number(entryProb ?? 0)} tone="entry" />
          <p className="text-[11px] text-mist leading-snug">
            Вероятность, что именно сейчас хорошая точка входа.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-line/60 bg-ink/25 px-3 py-2.5 space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <div className="text-[10px] uppercase tracking-wide text-mist flex items-center">
              Chasing Risk
              <HelpTip title="Chasing Risk">{CARD_HELP.chasing}</HelpTip>
            </div>
            <div
              className={`text-[11px] font-medium ${
                signal.chasing_level === "HIGH"
                  ? "text-rose-300"
                  : signal.chasing_level === "MEDIUM"
                    ? "text-amber-300"
                    : "text-emerald-300"
              }`}
            >
              {signal.chasing_level || "—"}
            </div>
          </div>
          <RiskBar value={Number(signal.chasing_risk ?? 0)} level={signal.chasing_level} />
          <div className="text-xs text-slate-200 tabular-nums">{signal.chasing_risk ?? "—"}%</div>
          <p className="text-[10px] text-mist leading-snug">
            {signal.chasing_hint || "Риск догона уже ушедшего движения"}
          </p>
        </div>
        <div className="rounded-lg border border-line/60 bg-ink/25 px-3 py-2.5 space-y-1">
          <div className="text-[10px] uppercase tracking-wide text-mist flex items-center">
            Smart Money
            <HelpTip title="Smart Money">{CARD_HELP.smartMoney}</HelpTip>
          </div>
          <div className="text-sm text-slate-100 font-medium">
            {signal.smart_money_activity || "—"}
          </div>
          <div className="text-amber-300/90 tracking-widest text-sm">
            {signal.smart_money_stars || starsFromScore(signal.smart_money_score || 30)}
          </div>
          <p className="text-[10px] text-mist leading-snug">
            {signal.smart_money_hint || signal.smart_money_ru || "Активность крупных игроков"}
          </p>
        </div>
      </div>

      <div className="rounded-lg border border-line/60 bg-ink/25 px-3 py-2 text-xs flex items-center justify-between gap-3">
        <div>
          <div className="text-mist uppercase tracking-wide text-[10px]">Liquidity Quality</div>
          <div className="text-amber-300/90 tracking-widest mt-0.5">
            {signal.liquidity_stars || starsFromScore(signal.liquidity_quality || 40)}
          </div>
        </div>
        <div className="text-right text-mist text-[11px] max-w-[55%]">
          {signal.liquidity_hint || "Оценка глубины и проскальзывания"}
        </div>
      </div>

      {Object.keys(breakdown).length > 0 && (
        <div className="rounded-lg border border-line/60 bg-ink/30 p-3 space-y-1">
          <div className="text-[10px] uppercase tracking-wide text-mist mb-1">
            Почему Execution {execution}
          </div>
          {Object.entries(breakdown).map(([name, part]) => {
            const p = part as { points?: number; max?: number };
            const pts = p.points ?? 0;
            const max = p.max ?? 1;
            const pct = Math.round((pts / max) * 100);
            return (
              <div key={name} className="grid grid-cols-[7rem_1fr_2.8rem] gap-2 items-center text-[11px]">
                <span className="text-mist truncate">{name}</span>
                <div className="h-1.5 rounded bg-line overflow-hidden">
                  <div className="h-full bg-sky-400/80" style={{ width: `${pct}%` }} />
                </div>
                <span className="tabular-nums text-right text-slate-300">
                  {pts}/{max}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {drivers.length > 0 && (
        <div className="rounded-lg border border-line/60 bg-ink/25 p-3 space-y-1.5">
          <div className="text-[10px] uppercase tracking-wide text-mist">
            Что сильнее всего влияет на оценку
          </div>
          {drivers.map((d) => (
            <div
              key={d.key}
              className={`flex justify-between text-xs ${
                d.impact >= 0 ? "text-emerald-300/90" : "text-rose-300/90"
              }`}
            >
              <span>
                {d.impact >= 0 ? "▲" : "▼"} {d.label}
              </span>
              <span className="tabular-nums font-medium">
                {d.impact > 0 ? `+${d.impact}` : d.impact}
              </span>
            </div>
          ))}
        </div>
      )}

      <Divider />

      <div className="grid grid-cols-2 gap-3 text-xs tabular-nums">
        <div>
          <div className="text-mist">Current</div>
          <div className="text-slate-100 mt-0.5">{fmt(signal.current_price)}</div>
        </div>
        <div>
          <div className="text-mist">Ideal Entry</div>
          <div className="text-slate-100 mt-0.5">
            {idealLow != null && idealHigh != null
              ? `${fmt(idealLow)}–${fmt(idealHigh)}`
              : fmt(ideal)}
          </div>
        </div>
      </div>

      <RangeLadder scale={signal.range_scale} />

      {why && (
        <div className="rounded-lg border border-amber-500/25 bg-amber-500/5 px-3 py-2.5 space-y-1.5">
          <div className="text-[10px] uppercase tracking-wide text-amber-100/80 flex items-center">
            {why.title}
            {signal.direction === "SHORT" && signal.pd_zone === "discount" ? (
              <HelpTip title="Discount и SHORT">{CARD_HELP.discountShort}</HelpTip>
            ) : (
              <HelpTip title="Почему нет входа">{CARD_HELP.timingLate}</HelpTip>
            )}
          </div>
          <ul className="space-y-1">
            {why.bullets.map((b) => (
              <li key={b} className="text-xs text-slate-100">
                • {b}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <div className="text-[10px] uppercase tracking-wide text-mist mb-1.5">Confirmed</div>
        <ul className="space-y-1">
          {confirmed.slice(0, 6).map((r) => (
            <li key={r} className="text-xs text-emerald-300/90">
              ✅ {r}
            </li>
          ))}
          {!confirmed.length && <li className="text-xs text-mist">—</li>}
        </ul>
      </div>

      <div>
        <div className="text-[10px] uppercase tracking-wide text-mist mb-1.5">Waiting For</div>
        <ul className="space-y-1">
          {(waiting.length
            ? waiting
            : (signal.next_steps || []).map((label) => ({ key: label, label, done: false }))
          ).map((w) => (
            <li
              key={w.key || w.label}
              className={`text-xs ${w.done ? "text-emerald-300/80" : "text-slate-200"}`}
            >
              {w.done ? "☑" : "□"} {w.label}
            </li>
          ))}
        </ul>
      </div>

      {invalidation.length > 0 && (
        <div className="rounded-lg border border-rose-500/25 bg-rose-950/20 px-3 py-2.5 space-y-1.5">
          <div className="text-[10px] uppercase tracking-wide text-rose-200/90 flex items-center">
            Invalidation
            <HelpTip title="Invalidation">{CARD_HELP.invalidation}</HelpTip>
          </div>
          <ul className="space-y-1">
            {invalidation.map((item) => (
              <li key={item.key || item.label} className="text-xs text-rose-100/90">
                ❌ {item.label}
              </li>
            ))}
          </ul>
        </div>
      )}

      {nextTrigger && (
        <div className="rounded-lg border border-sky-500/25 bg-sky-500/5 px-3 py-2.5 space-y-1.5 text-xs">
          <div className="text-[10px] uppercase tracking-wide text-sky-100/80">
            {nextTrigger.title}
          </div>
          <div className="text-mist">Если:</div>
          <ul className="space-y-1 text-slate-100">
            {nextTrigger.if_conditions.map((c) => (
              <li key={c}>✓ {c}</li>
            ))}
          </ul>
          <div className="pt-1 text-slate-200">
            ↓ Статус:{" "}
            <span className="text-mist">{nextTrigger.from_status.replaceAll("_", " ")}</span>
            {" → "}
            <span className="text-emerald-300 font-medium">
              {nextTrigger.to_status.replaceAll("_", " ")}
            </span>
          </div>
        </div>
      )}

      {history.length > 0 && (
        <div className="rounded-lg border border-line/60 bg-ink/20 px-3 py-2.5 space-y-2">
          <div className="text-[10px] uppercase tracking-wide text-mist">Последние изменения</div>
          {history.slice(0, 5).map((h, i) => (
            <div key={`${h.time}-${h.field}-${i}`} className="text-[11px] border-t border-line/40 pt-1.5 first:border-0 first:pt-0">
              <div className="flex justify-between text-slate-200">
                <span>
                  {h.time} · {h.field}
                </span>
                <span className="tabular-nums text-mist">
                  {String(h.from)} → {String(h.to)}
                </span>
              </div>
              <div className="text-mist mt-0.5">{h.reason}</div>
            </div>
          ))}
        </div>
      )}

      {(signal.replay || []).length > 0 && (
        <div className="rounded-lg border border-line/60 bg-ink/25 px-3 py-2.5 space-y-2">
          <div className="text-[10px] uppercase tracking-wide text-mist flex items-center">
            Replay
            <HelpTip title="Replay">{CARD_HELP.replay}</HelpTip>
          </div>
          <div className="space-y-1">
            {[...(signal.replay || [])].reverse().map((step, i, arr) => (
              <div key={`${step.time}-${step.status}-${i}`} className="text-xs text-slate-200">
                <div className="flex items-center gap-2">
                  <span className="text-mist tabular-nums w-10">{step.time}</span>
                  <span>
                    {step.emoji || ""} {(step.label || step.status || "").replaceAll("_", " ")}
                  </span>
                </div>
                {i < arr.length - 1 && <div className="pl-12 text-mist leading-none py-0.5">↓</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      <Divider />

      <div className="text-xs">
        <div className="text-[10px] uppercase tracking-wide text-mist mb-2 flex items-center">
          Trade Plan
          <HelpTip title="Trade Plan">{CARD_HELP.tradePlan}</HelpTip>
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 tabular-nums text-slate-200">
          <span>Ideal Entry {fmt(ideal)}</span>
          <span>Stop {fmt(signal.stop)}</span>
          <span>TP1 {fmt(tp1)}</span>
          <span>TP2 {fmt(signal.target)}</span>
          <span>RR {signal.risk_reward ?? "—"}</span>
          <span>Scenario Risk {signal.scenario_risk_pct ?? "—"}%</span>
        </div>
      </div>

      <Divider />

      <div className="text-xs space-y-1">
        <div className="text-[10px] uppercase tracking-wide text-mist">AI Verdict</div>
        <p className="text-slate-100 font-medium">{signal.ai_verdict || "🟡 Наблюдение"}</p>
        <div className="text-[10px] uppercase tracking-wide text-mist pt-1">AI Conclusion</div>
        <p className="text-slate-200 leading-relaxed">
          {signal.ai_conclusion || signal.ai_comment || "Ждём подтверждения."}
        </p>
      </div>

      <div className={`rounded-lg border px-3 py-2.5 text-xs ${STATUS_STYLE[life] || STATUS_STYLE.WATCH}`}>
        <div className="text-[10px] uppercase tracking-wide opacity-80 mb-1">Action</div>
        <div className="font-medium text-sm">
          {action?.emoji || emoji} {action?.title || "Сейчас не входить"}
        </div>
      </div>

      <div className="text-[11px] text-mist space-y-0.5">
        <p>⏳ Сценарий сформирован: {ageLabel(signal.created_at, liveAge)}</p>
        <p>⏳ Оценка актуальности: {signal.freshness_ru || "—"}</p>
        <p>⏳ Автопереоценка: каждые {signal.reeval_sec || 60} сек.</p>
      </div>

      <div className="flex gap-3 text-sm pt-1">
        <Link
          href={`/terminal?symbol=${signal.symbol}&exchange=${signal.exchange || "bybit"}`}
          className="text-accent hover:underline"
        >
          Терминал
        </Link>
        <Link href={`/signals/${signal.id}`} className="text-mist hover:text-white">
          Детали
        </Link>
      </div>
    </motion.article>
  );
}
