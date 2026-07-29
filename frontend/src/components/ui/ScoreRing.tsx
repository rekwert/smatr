"use client";

function scoreColor(score: number) {
  if (score >= 80) return "#00FF88";
  if (score >= 50) return "#FFC107";
  return "#FF4444";
}

export function ScoreRing({
  score,
  size = 72,
  label = "SCORE",
}: {
  score: number;
  size?: number;
  label?: string;
}) {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  const color = scoreColor(score);
  return (
    <div className="relative inline-flex flex-col items-center" style={{ width: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="#27272A" strokeWidth={6} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={color}
          strokeWidth={6}
          fill="none"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center rotate-0">
        <span className="font-display text-lg leading-none" style={{ color }}>
          {Math.round(score)}
        </span>
        <span className="text-[9px] uppercase tracking-wider text-mist mt-0.5">{label}</span>
      </div>
    </div>
  );
}

export function ConfidenceMeter({ value }: { value: number }) {
  const v = Math.max(0, Math.min(100, value));
  return (
    <div>
      <div className="flex justify-between text-xs text-mist mb-1">
        <span>Уверенность AI</span>
        <span>{Math.round(v)}%</span>
      </div>
      <div className="h-2 rounded-full bg-white/10 overflow-hidden">
        <div className="h-full rounded-full bg-accent" style={{ width: `${v}%` }} />
      </div>
    </div>
  );
}

export function RiskMeter({ level }: { level: string }) {
  const map: Record<string, { pct: number; color: string; label: string }> = {
    low: { pct: 30, color: "#00FF88", label: "НИЗКИЙ" },
    medium: { pct: 55, color: "#FFC107", label: "СРЕДНИЙ" },
    high: { pct: 85, color: "#FF4444", label: "ВЫСОКИЙ" },
  };
  const m = map[level.toLowerCase()] || map.medium;
  return (
    <div>
      <div className="flex justify-between text-xs text-mist mb-1">
        <span>Риск</span>
        <span style={{ color: m.color }}>{m.label}</span>
      </div>
      <div className="h-2 rounded-full bg-white/10 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${m.pct}%`, background: m.color }} />
      </div>
    </div>
  );
}
