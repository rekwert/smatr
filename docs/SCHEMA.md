# Part 14 — Database Schema (SaaS foundation)

Storage is split across three layers so market volume does not crush app OLTP.

```
DATA SOURCES → INGESTION
                  ├── PostgreSQL   (users, signals, trades, AI meta)
                  ├── TimescaleDB  (market_candles hypertable + hot market tables)
                  └── Redis        (prices, active signals, queues, last OB)
                         ↓
                   Analytics / AI Engine
```

## PostgreSQL modules

| Area | Tables |
|------|--------|
| Users | `users`, `user_settings`, `exchange_accounts` |
| Registry | `exchanges`, `symbols`, `exchange_symbols` |
| Signals | `signals`, `trade_plans`, `smart_money_events`, `candidates` |
| Trading | `trades`, `trade_reviews`, `trade_journal` |
| AI | `ai_models`, `training_samples`, `ai_predictions`, `market_memory` |
| System | `notifications`, `system_logs`, `signal_feedback`, `strategies`, `backtest_results` |

Roles: `USER` | `PRO` | `ADMIN` | `SYSTEM`

Exchanges seeded: bybit, okx, bitget, mexc, bingx, kucoin

## Market / Timescale path

| Table | Purpose | Retention (policy) |
|-------|---------|-------------------|
| `market_candles` | Multi-exchange OHLCV (hypertable on `time`) | up to 10y (TF-specific in app) |
| `candles` | Legacy MVP (`symbol_id`) | scanner compat |
| `market_trades` | Tape / delta / whales | 6 months |
| `orderbook_snapshots` | Aggregated OB metrics only | 30 days |
| `derivatives_data` | OI + funding | keep with candles |
| `indicators` | Precomputed features | research |

Bootstrap: `init_db()` → `create_all` → seed exchanges → Timescale hypertable + indexes  
(`docker/init-db.sql`, `docker/init-timescale.sql`, `app/database/connection.py`).

## Redis keys

| Key | Example |
|-----|---------|
| price | `price:bybit:BTCUSDT` |
| ticker | `ticker:bybit:XYZUSDT` |
| orderbook | `orderbook:bybit:XYZUSDT` |
| candles last | `candles:bybit:BTCUSDT:15m:last` |
| active signals | `signal:active` |
| scanner queue | `scanner:queue` |

Helpers: `app/market_data/redis_cache.py`, constants in `app/database/retention.py`.

## Growth targets

| Tier | Symbols | Candles |
|------|---------|---------|
| MVP | ~1k | ~100M |
| PRO | ~10k | billions (partition / hypertable) |

## Code map

- Models: `backend/app/database/models.py`
- Repositories: `backend/app/database/repositories.py`
- Retention / Redis templates: `backend/app/database/retention.py`

**Note:** Existing local DBs created before Part 14 may need recreate (`docker compose down -v` + up) — Alembic migrations are not the primary path yet (`create_all` + Timescale SQL).
