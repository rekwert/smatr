# Smart Money AI Scanner (SMAS)

Интеллектуальный сканер крипторынка по **Bybit Linear USDT Perpetual**.

Главный экран — **лучшие возможности**, не лента графиков.  
Система **не торгует автоматически** и **не гарантирует прибыль**.

## Стек

| Layer | Tech |
|-------|------|
| Exchange | **Bybit V5** (REST + WS linear); Binance/OKX stubs |
| Backend | Python 3.12, FastAPI, SQLAlchemy, Celery, Redis |
| AI | Context Builder + LLM (optional) + template fallback |
| DB | PostgreSQL + TimescaleDB |
| Frontend | Next.js 15, TypeScript, Tailwind, Lightweight Charts |
| Alerts | Telegram bot (aiogram 3) |

## Быстрый старт

```bash
docker compose up -d postgres redis
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# frontend
cd frontend && npm install && npm run dev
# telegram (optional)
set TELEGRAM_BOT_TOKEN=...
set SMAS_API_URL=http://localhost:8000
python -m telegram_bot.bot
```

## Parts 1–8

| Part | Status |
|------|--------|
| 1 PRD | Done |
| 2 Engines | Done |
| 3 Backend | Done |
| 4 Frontend | Done |
| 5 AI Engine | Done (template + LLM hook) |
| 6 Backtesting | Done (simulator + metrics + research UI) |
| 7 Data Pipeline | Done (base iface, validate, OB, regime, anomaly, redis) |
| 8 Notifications + Telegram | Done (tiers, antispam, bot, feedback) |

## Key APIs

- `POST /api/v1/ai/explain` `{signal_id, mode: explain|plan|similar|market}`
- `POST /api/v1/ai/market-analysis`
- `POST /api/v1/ai/review`
- `GET  /api/v1/ai/scanner-assistant`
- `POST /api/v1/backtest/run` — real SMC/Pump replay
- `GET  /api/v1/data/health`
- `GET  /api/v1/data/orderbook/{symbol}`
- `POST /api/v1/notifications/feedback`
- `PUT  /api/v1/notifications/settings`

Docs: `docs/PLAN.md`, `docs/ARCHITECTURE.md`, `docs/PATTERNS.md`

## Part 9 Multi-Exchange

```
GET  /api/v1/exchanges/status
GET  /api/v1/exchanges/universe
GET  /api/v1/exchanges/lowcap
GET  /api/v1/exchanges/new-listings
GET  /api/v1/exchanges/{exchange}/candles/{symbol}
GET  /api/v1/exchanges/{exchange}/analyze/{symbol}  # SMC+Pump on unified candles
POST /api/v1/exchanges/sync-symbols
```

Connectors: Bybit, OKX, Bitget, MEXC, BingX, KuCoin → `MarketDataEngine` → SMC / Pump / AI.

## Parts 10–13

| Part | API / UI |
|------|----------|
| 10 Low Cap Hunter | `GET /api/v1/pump-hunter` · `/hunter` |
| 11 Strategy + Risk | `POST /api/v1/trade-plan/create` |
| 12 Trading Terminal | `/terminal` (chart + AI + plan, confirm mode) |
| 13 Quant ML + Decision | `POST /api/v1/ml/analyze` |

```bash
curl "http://localhost:8000/api/v1/pump-hunter?analyze_top=10"
curl -X POST http://localhost:8000/api/v1/trade-plan/create -H "Content-Type: application/json" -d "{\"symbol\":\"BTCUSDT\",\"exchange\":\"bybit\"}"
curl -X POST http://localhost:8000/api/v1/ml/analyze -H "Content-Type: application/json" -d "{\"symbol\":\"BTCUSDT\",\"exchange\":\"bybit\"}"
```

## Part 14 — Database

PostgreSQL + TimescaleDB + Redis. Full schema: [`docs/SCHEMA.md`](docs/SCHEMA.md).

| Layer | Stores |
|-------|--------|
| PostgreSQL | users, exchanges, signals, trade plans, trades, AI models/samples |
| Timescale | `market_candles` hypertable (+ market trades / OB snapshots) |
| Redis | `price:*`, `signal:active`, `scanner:queue`, last orderbook |

On API start, `init_db()` creates tables, seeds 6 exchanges, and applies Timescale hypertable/indexes when available.

Docs: `docs/PLAN.md`, `docs/ARCHITECTURE.md`, `docs/PATTERNS.md`, `docs/SCHEMA.md`
