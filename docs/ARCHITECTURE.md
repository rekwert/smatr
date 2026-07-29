# Architecture

## Runtime (MVP)

Модульный **монолит** FastAPI + Celery + Next.js. Логические «сервисы» из ТЗ живут как пакеты в одном процессе (готовы к выносу в микросервисы позже).

```
FRONTEND (RU)  →  API Gateway (FastAPI /api/v1 + WS)
                      │
   Auth │ Market │ Scanner │ SMC │ AI │ Strategy │ Trading* │ Notify
                      │
         PostgreSQL + TimescaleDB + Redis (+ RabbitMQ profile:full)
                      │
         Bybit / OKX / Bitget / MEXC / BingX / KuCoin
```

\*Trading = планы + confirmation mode; live-ордера — PRO.

| ТЗ-сервис | Код |
|-----------|-----|
| API Gateway | `backend/app/api/`, `main.py`, `ws.py` |
| Auth | `api/routes/auth.py`, `core/security.py` |
| Exchange | `exchange_layer/` |
| Market Data | `market_data/`, `exchange_layer/market_data_engine.py` |
| Scanner | `services/scanner.py`, `engines/hunter/` |
| SMC | `engines/structure|liquidity|fvg|order_blocks|volume` |
| AI | `ai/`, `ml/` — **ответы на русском** |
| Strategy | `strategy/` |
| Trading | `api/routes/trade_plan.py` (confirm) |
| Notifications | `notifications/`, `telegram_bot/` — **RU** |
| Backtest | `backtesting/` |
| Events | `core/events.py` (Redis pub/sub; RabbitMQ optional) |

## Locale

- Сайт, Telegram и AI-промпты / fallback — **русский**.
- Технические идентификаторы API (LONG, score, symbol) без перевода.

## Sequence rule

1. Liquidity → 2. BOS/CHoCH → 3. FVG/OB → 4. Volume/OI → 5. Risk plan

## Score tiers

| Score | Tier | Notify |
|------|------|--------|
| 90–94 | high | Telegram |
| 95–100 | elite | instant Telegram |

## Growth path

1. MVP monolith (сейчас)  
2. **Market Universe Engine v2** (6 бирж → cheap filter → SMC/AI)  
3. RabbitMQ consumers + split workers  
4. K8s + Prometheus/Grafana  
5. Live trading + Mini App

### Universe v2 funnel

```
5000–7000 USDT perps (6 exchanges)
        ↓ L2 cheap filter
   100–200 candidates (Tier A/B/C)
        ↓ L3 heavy
    50–100 scored
        ↓
     5–15 trade ideas + cross-exchange gaps
```
