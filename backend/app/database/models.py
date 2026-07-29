"""SQLAlchemy models — Part 14 SaaS database foundation.

PostgreSQL: users, exchanges, signals, trades, AI meta
Timescale-oriented: market_candles, market_trades, orderbook_snapshots, derivatives_data
Legacy: candles (symbol_id) — kept for current scanner pipeline
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(30), default="USER")  # USER | PRO | ADMIN | SYSTEM
    subscription: Mapped[str] = mapped_column(String(32), default="free")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    risk_level: Mapped[str] = mapped_column(String(20), default="medium")
    max_positions: Mapped[int] = mapped_column(Integer, default=5)
    daily_loss_limit: Mapped[float] = mapped_column(Float, default=3.0)
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    min_score: Mapped[int] = mapped_column(Integer, default=90)
    notify_pumps: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_smc: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_breakouts: Mapped[bool] = mapped_column(Boolean, default=False)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExchangeAccount(Base):
    """Encrypted user API keys — never store plaintext."""

    __tablename__ = "exchange_accounts"
    __table_args__ = (UniqueConstraint("user_id", "exchange", name="uq_user_exchange"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    exchange: Mapped[str] = mapped_column(String(50))
    api_key_encrypted: Mapped[str] = mapped_column(Text)
    secret_encrypted: Mapped[str] = mapped_column(Text)
    passphrase_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="inactive")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Exchanges & symbols
# ---------------------------------------------------------------------------


class Exchange(Base):
    __tablename__ = "exchanges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    type: Mapped[str] = mapped_column(String(30), default="futures")
    api_status: Mapped[str] = mapped_column(String(20), default="unknown")
    latency_ms: Mapped[Optional[float]] = mapped_column("latency", Float, nullable=True)
    last_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Symbol(Base):
    """Canonical symbol registry (per exchange)."""

    __tablename__ = "symbols"
    __table_args__ = (UniqueConstraint("exchange", "symbol", name="uq_exchange_symbol"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exchange_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("exchanges.id"), nullable=True)
    exchange: Mapped[str] = mapped_column(String(50), default="bybit", index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    base_asset: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    quote_asset: Mapped[str] = mapped_column(String(20), default="USDT")
    market_type: Mapped[str] = mapped_column(String(20), default="future")
    market_cap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    candles: Mapped[list["Candle"]] = relationship(back_populates="symbol_ref")


class ExchangeSymbol(Base):
    """Scanner snapshot ranking (liquidity scores)."""

    __tablename__ = "exchange_symbols"
    __table_args__ = (UniqueConstraint("exchange", "symbol", name="uq_ex_sym"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(50), index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    volume_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    liquidity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    listed_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Market data (legacy + Timescale path)
# ---------------------------------------------------------------------------


class Candle(Base):
    """Legacy per-symbol_id candles used by MVP scanner."""

    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("symbol_id", "timeframe", "timestamp", name="uq_candle"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    timeframe: Mapped[str] = mapped_column(String(10), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[int] = mapped_column(BigInteger, index=True)

    symbol_ref: Mapped["Symbol"] = relationship(back_populates="candles")


class MarketCandle(Base):
    """Multi-exchange OHLCV — Timescale hypertable on `time`.

    PK includes `time` so create_hypertable() is valid under Timescale rules.
    """

    __tablename__ = "market_candles"
    __table_args__ = (
        UniqueConstraint("exchange", "symbol", "timeframe", "time", name="uq_market_candle"),
    )

    time: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), primary_key=True)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(30), index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    timeframe: Mapped[str] = mapped_column(String(10), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)


class MarketTrade(Base):
    __tablename__ = "market_trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(30), index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)
    side: Mapped[str] = mapped_column(String(10))
    timestamp: Mapped[int] = mapped_column(BigInteger, index=True)


class OrderbookSnapshot(Base):
    __tablename__ = "orderbook_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(30), index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    bid_volume: Mapped[float] = mapped_column(Float, default=0)
    ask_volume: Mapped[float] = mapped_column(Float, default=0)
    spread: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    imbalance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp: Mapped[int] = mapped_column(BigInteger, index=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class DerivativesData(Base):
    __tablename__ = "derivatives_data"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(30), index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    open_interest: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    funding_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp: Mapped[int] = mapped_column(BigInteger, index=True)


class Indicator(Base):
    __tablename__ = "indicators"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(30), default="bybit")
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))
    atr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rsi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ema20: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ema50: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    extras: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    timestamp: Mapped[int] = mapped_column(BigInteger, index=True)


# ---------------------------------------------------------------------------
# Smart money / hunter / signals
# ---------------------------------------------------------------------------


class MarketEvent(Base):
    """Legacy events table (kept). Prefer SmartMoneyEvent for new writes."""

    __tablename__ = "market_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    strength: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SmartMoneyEvent(Base):
    __tablename__ = "smart_money_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(30), default="bybit")
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    strength: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    timestamp: Mapped[int] = mapped_column(BigInteger, index=True)


class Candidate(Base):
    """Low Liquidity Hunter candidates."""

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    exchange: Mapped[str] = mapped_column(String(30), index=True)
    liquidity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pump_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accumulation_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="SLEEPING", index=True)
    reasons: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    timestamp: Mapped[int] = mapped_column(BigInteger, index=True)


class LiquidityZone(Base):
    __tablename__ = "liquidity_zones"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    zone_type: Mapped[str] = mapped_column(String(32))
    price: Mapped[float] = mapped_column(Float)
    strength: Mapped[float] = mapped_column(Float, default=0)
    timeframe: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    exchange: Mapped[str] = mapped_column(String(30), default="bybit")
    direction: Mapped[str] = mapped_column(String(10))
    signal_type: Mapped[str] = mapped_column(String(32), default="smc")
    strategy: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    score: Mapped[int] = mapped_column(Integer, index=True)
    confidence: Mapped[str] = mapped_column(String(20), default="medium")
    timeframe: Mapped[str] = mapped_column(String(10), default="15")
    entry: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entry_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    stop: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    targets: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    risk_reward: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reason: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    zones: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TradePlan(Base):
    __tablename__ = "trade_plans"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    signal_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    exchange: Mapped[str] = mapped_column(String(30), default="bybit")
    direction: Mapped[str] = mapped_column(String(10))
    setup: Mapped[str] = mapped_column(String(64), default="unknown")
    entry: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    stop: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    targets: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    risk: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_reward: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="WATCHING", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# User trades & journal
# ---------------------------------------------------------------------------


class Trade(Base):
    """Executed / journaled user trades."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    exchange: Mapped[str] = mapped_column(String(30), default="bybit")
    side: Mapped[str] = mapped_column(String(10))
    entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    result: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    plan_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    signal_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class TradeReview(Base):
    __tablename__ = "trade_reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trade_id: Mapped[int] = mapped_column(BigInteger, index=True)
    ai_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mistakes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    lessons: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TradeJournal(Base):
    """Lightweight journal entries (legacy-compatible)."""

    __tablename__ = "trade_journal"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    symbol: Mapped[str] = mapped_column(String(50))
    setup: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    entry: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    result_r: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# AI / training loop
# ---------------------------------------------------------------------------


class AIModel(Base):
    __tablename__ = "ai_models"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[str] = mapped_column(String(20))
    accuracy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    artifact_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TrainingSample(Base):
    __tablename__ = "training_samples"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    exchange: Mapped[str] = mapped_column(String(30), default="bybit")
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    label: Mapped[str] = mapped_column(String(30), index=True)
    future_result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIPrediction(Base):
    __tablename__ = "ai_predictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    model: Mapped[str] = mapped_column(String(50))
    prediction: Mapped[float] = mapped_column(Float)
    actual_result: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    timestamp: Mapped[int] = mapped_column(BigInteger, index=True)


class MarketMemory(Base):
    __tablename__ = "market_memory"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    setup_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    avg_rr: Mapped[float] = mapped_column(Float, default=0)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------


class NotificationLog(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    signal_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(32), default="telegram")
    type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="sent")
    sent: Mapped[bool] = mapped_column(Boolean, default=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SignalFeedback(Base):
    __tablename__ = "signal_feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    signal_id: Mapped[int] = mapped_column(BigInteger, index=True)
    vote: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    service: Mapped[str] = mapped_column(String(50), index=True)
    level: Mapped[str] = mapped_column(String(20), default="INFO")
    message: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    strategy: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(50))
    period: Mapped[str] = mapped_column(String(64))
    winrate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    profit_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    drawdown: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trades: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    kind: Mapped[str] = mapped_column(String(50), default="smc")
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
