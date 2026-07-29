"""Part 14 — schema / retention smoke tests (no live DB required)."""

from __future__ import annotations

from app.database import models
from app.database.retention import REDIS_KEYS, RETENTION
from app.market_data.redis_cache import RedisCache


REQUIRED_TABLES = {
    "users",
    "user_settings",
    "exchange_accounts",
    "exchanges",
    "symbols",
    "market_candles",
    "market_trades",
    "orderbook_snapshots",
    "derivatives_data",
    "indicators",
    "smart_money_events",
    "candidates",
    "signals",
    "trade_plans",
    "trades",
    "trade_reviews",
    "ai_models",
    "training_samples",
    "ai_predictions",
    "system_logs",
}


def test_part14_models_registered():
    names = set(models.Base.metadata.tables.keys())
    missing = REQUIRED_TABLES - names
    assert not missing, f"missing tables: {missing}"


def test_part14_market_candle_pk_includes_time():
    cols = {c.name for c in models.MarketCandle.__table__.primary_key.columns}
    assert "time" in cols
    assert "id" in cols


def test_part14_retention_keys():
    assert "market_candles_1m" in RETENTION
    assert "orderbook_snapshots" in RETENTION
    assert REDIS_KEYS["price"].startswith("price:")


def test_part14_redis_key_helpers():
    assert RedisCache.price_key("bybit", "BTCUSDT") == "price:bybit:BTCUSDT"
    assert RedisCache.active_signals_key() == "signal:active"
    assert "scanner:queue" in RedisCache.key_templates().values()


def test_part14_user_roles_default():
    assert models.User.__table__.c.role.default.arg == "USER"
