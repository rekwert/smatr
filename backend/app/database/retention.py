"""Part 14 — Database architecture plan & retention.

Layers:
  PostgreSQL  → users, settings, exchanges, signals, trades, AI meta
  TimescaleDB → market_candles (hypertable), optional ticks
  Redis       → prices, active signals, queues, orderbook snapshots

Legacy `candles` (symbol_id FK) kept for MVP scanner compatibility.
Canonical multi-exchange OHLCV: `market_candles`.
"""

RETENTION = {
    "market_candles_1m": "2 years",
    "market_candles_5m": "5 years",
    "market_candles_1h": "10 years",
    "orderbook_snapshots": "30 days",
    "market_trades": "6 months",
    "system_logs": "90 days",
    "ai_predictions": "2 years",
}

REDIS_KEYS = {
    "price": "price:{exchange}:{symbol}",
    "ticker": "ticker:{exchange}:{symbol}",
    "signal_active": "signal:active",
    "scanner_queue": "scanner:queue",
    "orderbook": "orderbook:{exchange}:{symbol}",
    "candles_last": "candles:{exchange}:{symbol}:{tf}:last",
    "notify_cooldown": "notify:{symbol}:{signal_type}",
}
