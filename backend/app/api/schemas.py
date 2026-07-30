from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ReasonBlock(BaseModel):
    found: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    checklist: dict[str, bool] = Field(default_factory=dict)


class SignalOut(BaseModel):
    id: int
    symbol: str
    direction: str
    signal_type: str
    score: int
    confidence: str
    timeframe: str
    exchange: Optional[str] = "bybit"
    entry: Optional[float] = None
    stop: Optional[float] = None
    target: Optional[float] = None
    risk_reward: Optional[float] = None
    risk_pct: Optional[float] = None
    reason: dict[str, Any] = Field(default_factory=dict)
    zones: dict[str, Any] = Field(default_factory=dict)
    explanation: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    # Dual-score card v3
    setup_score: Optional[int] = None
    execution_score: Optional[int] = None
    overall_score: Optional[int] = None
    overall_formula: Optional[str] = None
    setup_stars: Optional[str] = None
    execution_stars: Optional[str] = None
    probability: Optional[int] = None
    scenario_probability: Optional[int] = None
    entry_probability_now: Optional[int] = None
    lifecycle_status: Optional[str] = None
    lifecycle_emoji: Optional[str] = None
    lifecycle_ru: Optional[str] = None
    lifecycle_hint: Optional[str] = None
    phase: Optional[str] = None
    phase_ru: Optional[str] = None
    progress: list[dict[str, Any]] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    waiting_for: list[dict[str, Any]] = Field(default_factory=list)
    ai_comment: Optional[str] = None
    ai_conclusion: Optional[str] = None
    ai_verdict: Optional[str] = None
    zone_note: Optional[str] = None
    why_no_entry: Optional[dict[str, Any]] = None
    invalidation: list[dict[str, Any]] = Field(default_factory=list)
    confidence_drivers: list[dict[str, Any]] = Field(default_factory=list)
    next_trigger: Optional[dict[str, Any]] = None
    range_scale: Optional[dict[str, Any]] = None
    liquidity_quality: Optional[int] = None
    liquidity_stars: Optional[str] = None
    liquidity_hint: Optional[str] = None
    chasing_risk: Optional[int] = None
    chasing_level: Optional[str] = None
    chasing_level_ru: Optional[str] = None
    chasing_hint: Optional[str] = None
    smart_money_activity: Optional[str] = None
    smart_money_ru: Optional[str] = None
    smart_money_score: Optional[int] = None
    smart_money_stars: Optional[str] = None
    smart_money_hint: Optional[str] = None
    edge_score: Optional[int] = None
    edge_stars: Optional[str] = None
    edge_reasons: list[str] = Field(default_factory=list)
    edge_hint: Optional[str] = None
    feed: Optional[str] = None  # inefficiency | volume_scan
    replay: list[dict[str, Any]] = Field(default_factory=list)
    score_history: list[dict[str, Any]] = Field(default_factory=list)
    status_reason: Optional[str] = None
    risk_label: Optional[str] = None
    scenario_risk_pct: Optional[int] = None
    current_price: Optional[float] = None
    distance_pct: Optional[float] = None
    distance_label: Optional[str] = None
    action: Optional[dict[str, Any]] = None
    freshness: Optional[str] = None
    freshness_ru: Optional[str] = None
    age_sec: Optional[int] = None
    age_label: Optional[str] = None
    reeval_sec: Optional[int] = 60
    tp1: Optional[float] = None
    timing: Optional[str] = None
    timing_emoji: Optional[str] = None
    timing_ru: Optional[str] = None
    timing_reason: Optional[str] = None
    traffic_lights: Optional[dict[str, Any]] = None
    execution_breakdown: Optional[dict[str, Any]] = None
    ideal_entry: Optional[float] = None
    ideal_entry_low: Optional[float] = None
    ideal_entry_high: Optional[float] = None
    alternative_entry_low: Optional[float] = None
    alternative_entry_high: Optional[float] = None
    pd_zone: Optional[str] = None
    plan_valid: Optional[bool] = None
    plan_note: Optional[str] = None
    invalidation_level: Optional[float] = None

    model_config = {"from_attributes": True}


class ScannerTopOut(BaseModel):
    smc_setups: list[SignalOut]
    pump_candidates: list[SignalOut]
    disclaimer: str


class MarketStatusOut(BaseModel):
    btc_trend: str
    volatility: str
    volume_spike_count: int
    active_signals: int


class BacktestRequest(BaseModel):
    strategy: str = "smc"
    symbol: str = "BTCUSDT"
    timeframe: str = "15"
    period: str = "2024-2026"
    risk_pct: float = 1.0


class BacktestOut(BaseModel):
    id: int
    strategy: str
    symbol: str
    period: str
    winrate: Optional[float]
    profit_factor: Optional[float]
    drawdown: Optional[float]
    trades: Optional[int]
    metrics: dict[str, Any] = Field(default_factory=dict)
