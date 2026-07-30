export type LifecycleStatus =
  | "IGNORE"
  | "WATCH"
  | "SETUP_FORMING"
  | "ENTRY_ZONE"
  | "ENTRY_READY"
  | "IN_POSITION"
  | "TP1_HIT"
  | "TP2_HIT"
  | "INVALIDATED"
  | string;

export type WaitingItem = {
  key: string;
  label: string;
  done: boolean;
};

export type SignalAction = {
  code: string;
  emoji: string;
  title: string;
  reason?: string;
  bullets: string[];
};

export type ProgressRow = {
  key: string;
  label: string;
  pct: number;
  bar?: string;
};

export type WhyNoEntry = {
  title: string;
  bullets: string[];
};

export type ConfidenceDriver = {
  key: string;
  label: string;
  impact: number;
  direction: "up" | "down" | string;
};

export type NextTrigger = {
  title: string;
  if_conditions: string[];
  from_status: string;
  to_status: string;
  note?: string;
};

export type RangeScale = {
  high: number;
  low: number;
  mid?: number;
  price?: number | null;
  ideal_low?: number | null;
  ideal_high?: number | null;
  ideal_mid?: number | null;
  price_pct?: number | null;
  ideal_low_pct?: number | null;
  ideal_high_pct?: number | null;
  ideal_mid_pct?: number | null;
  mid_pct?: number | null;
  zone?: string | null;
};

export type ScoreChange = {
  time: string;
  field: string;
  from: string | number | null;
  to: string | number | null;
  reason: string;
};

export type Signal = {
  id: number;
  symbol: string;
  exchange?: string | null;
  direction: "LONG" | "SHORT" | string;
  signal_type: "smc" | "pump" | string;
  score: number;
  confidence: string;
  timeframe: string;
  entry?: number | null;
  stop?: number | null;
  target?: number | null;
  tp1?: number | null;
  risk_reward?: number | null;
  risk_pct?: number | null;
  reason?: {
    found?: string[];
    missing?: string[];
    checklist?: Record<string, boolean>;
    confirmed?: string[];
    missing_items?: string[];
    pump?: {
      total?: number;
      reasons?: string[];
      status?: string;
    };
  };
  zones?: Record<string, unknown>;
  explanation?: string | null;
  status: string;
  created_at?: string | null;
  setup_score?: number | null;
  execution_score?: number | null;
  overall_score?: number | null;
  overall_formula?: string | null;
  setup_stars?: string | null;
  execution_stars?: string | null;
  probability?: number | null;
  scenario_probability?: number | null;
  entry_probability_now?: number | null;
  lifecycle_status?: LifecycleStatus | null;
  lifecycle_emoji?: string | null;
  lifecycle_ru?: string | null;
  lifecycle_hint?: string | null;
  phase?: string | null;
  phase_ru?: string | null;
  progress?: ProgressRow[];
  waiting_for?: WaitingItem[];
  next_steps?: string[];
  ai_comment?: string | null;
  ai_conclusion?: string | null;
  zone_note?: string | null;
  why_no_entry?: WhyNoEntry | null;
  invalidation?: { key?: string; label: string }[];
  confidence_drivers?: ConfidenceDriver[];
  next_trigger?: NextTrigger | null;
  range_scale?: RangeScale | null;
  liquidity_quality?: number | null;
  liquidity_stars?: string | null;
  liquidity_hint?: string | null;
  chasing_risk?: number | null;
  chasing_level?: string | null;
  chasing_level_ru?: string | null;
  chasing_hint?: string | null;
  smart_money_activity?: string | null;
  smart_money_ru?: string | null;
  smart_money_score?: number | null;
  smart_money_stars?: string | null;
  smart_money_hint?: string | null;
  edge_score?: number | null;
  edge_stars?: string | null;
  edge_reasons?: string[];
  edge_hint?: string | null;
  inefficiency_type?: string | null;
  inefficiency_type_ru?: string | null;
  inefficiency_strength?: number | null;
  inefficiency_thesis?: string | null;
  inefficiency_status?: string | null;
  inefficiency_status_ru?: string | null;
  inefficiency_qualifies?: boolean | null;
  inefficiency_playbook?: { key?: string; label?: string; done?: boolean; required?: boolean }[];
  relative_volume?: number | null;
  displacement_pct?: number | null;
  entry_blockers?: string[];
  replay?: { time: string; status: string; label?: string; emoji?: string }[];
  score_history?: ScoreChange[];
  risk_label?: string | null;
  scenario_risk_pct?: number | null;
  current_price?: number | null;
  distance_pct?: number | null;
  distance_label?: string | null;
  action?: SignalAction | null;
  freshness?: string | null;
  freshness_ru?: string | null;
  age_sec?: number | null;
  age_label?: string | null;
  reeval_sec?: number | null;
  timing?: string | null;
  timing_emoji?: string | null;
  timing_ru?: string | null;
  timing_reason?: string | null;
  traffic_lights?: Record<string, string> | null;
  execution_breakdown?: {
    total?: number;
    parts?: Record<string, { points?: number; max?: number }>;
  } | null;
  ideal_entry?: number | null;
  ideal_entry_low?: number | null;
  ideal_entry_high?: number | null;
  alternative_entry_low?: number | null;
  alternative_entry_high?: number | null;
  pd_zone?: string | null;
  status_reason?: string | null;
  ai_verdict?: string | null;
};

export type MarketStatus = {
  btc_trend: string;
  volatility: string;
  volume_spike_count: number;
  active_signals: number;
};

export type Candle = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};
