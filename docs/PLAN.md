# Smart Money AI Scanner — Implementation Plan (Parts 1–8)

**Repo:** `smart-money-ai-scanner`  
**Primary exchange:** Bybit V5 Linear (USDT Perpetual)  
**Binance/OKX:** adapter stubs only (Part 7 interface)

---

## Parts 1–4

Delivered (PRD, engines, backend, frontend). See git history / README.

---

## Part 5 — AI Engine

| Module | Path | MVP |
|--------|------|-----|
| Context Builder | `ai/context_builder.py` | Yes |
| Prompt templates | `ai/prompts/*.txt` | Yes |
| LLM client + structured JSON | `ai/llm.py` | Yes (fallback template) |
| Explain / Plan / Market / Similar | `ai/engine.py` | Yes |
| Hallucination guard | `ai/guards.py` | Yes |
| Rating Engine | `ai/rating.py` | Yes |
| Memory (market/trader) | `ai/memory.py` + DB | Yes (store/query) |
| Similar setups (fingerprint) | `ai/similar.py` | Yes (DB signals, not vector yet) |
| API | `POST /api/v1/ai/*` | Yes |
| Vector DB / fine-tune | — | Later (2.0) |

**Principle:** AI never searches trades alone — only explains engine context.

---

## Part 6 — Backtesting & Research

| Module | Path | MVP |
|--------|------|-----|
| Trade Simulator | `backtesting/simulator.py` | Yes |
| Metrics | `backtesting/metrics.py` | Yes |
| SMC/Pump replay | `backtesting/engine.py` | Yes |
| Historical load from Bybit/DB | `backtesting/data_loader.py` | Yes |
| Research API + dashboard | routes + frontend | Yes |
| Walk-forward / Monte Carlo / ML | — | Later |

---

## Part 7 — Data Pipeline & Market Intelligence

| Module | Path | MVP |
|--------|------|-----|
| Exchange base interface | `exchanges/base.py` | Yes |
| Bybit implements base | `exchanges/bybit.py` | Yes |
| Binance/OKX stubs | `exchanges/binance.py`, `okx.py` | Stubs |
| Candle validation | `market_data/validation.py` | Yes |
| Symbol discovery filters | `market_data/symbol_discovery.py` | Yes |
| Orderbook metrics | `market_data/orderbook.py` | Yes |
| Volume intelligence / RV | `market_data/volume_intelligence.py` | Yes |
| Market regime | `engines/regime/` | Yes |
| Anomaly detector | `engines/anomaly/` | Yes |
| Redis hot cache | `market_data/redis_cache.py` | Yes |
| Data health | `api/routes/health_data.py` | Yes |
| Kafka | — | Scale later |

---

## Part 8 — Notifications + Telegram

| Module | Path | MVP |
|--------|------|-----|
| Notification manager + tiers | `notifications/manager.py` | Yes |
| Templates | `notifications/templates/` | Yes |
| Anti-spam / cooldown | `notifications/anti_spam.py` | Yes |
| User settings + feedback | models + API | Yes |
| Telegram bot (aiogram 3) | `telegram_bot/` | Yes |
| Mini App / Voice | — | Later |

---

## Part 9 — Multi-Exchange Data Aggregation

| Module | Path | Status |
|--------|------|--------|
| Unified interface + models | `exchange_layer/base/` | Done |
| Connectors: Bybit, OKX, Bitget, MEXC, BingX, KuCoin | `exchange_layer/connectors/` | Done |
| Normalizer | `exchange_layer/normalizer/` | Done |
| WS manager + reconnect/heartbeat | `exchange_layer/websocket/` | Done (REST poll MVP) |
| Rate limiter | `exchange_layer/rate_limiter.py` | Done |
| Health / latency | `exchange_layer/monitoring/` | Done |
| Liquidity / LowCap / NewListing | `exchange_layer/scanners.py` | Done |
| MarketDataEngine → SMC/Pump/AI | `exchange_layer/market_data_engine.py` | Done |
| API `/api/v1/exchanges/*` | `api/routes/exchanges.py` | Done |

**Principle:** Engines never call raw exchange APIs — only unified MarketDataEngine / adapters.

**MVP priority:** Bybit → OKX → Bitget → MEXC → BingX → KuCoin

---

## Parts 10–13 (this iteration)

### Part 10 — Low Liquidity Coin Hunter
| Module | Path | MVP |
|--------|------|-----|
| Universe filter + Liquidity Score | `engines/hunter/` | Yes |
| Accumulation / ATR / Volume / Whale heuristics | same | Yes |
| False pump + Quality + statuses | same | Yes |
| API `GET /api/v1/pump-hunter` | routes | Yes |
| UI Low Cap Hunter | `/hunter` | Yes |
| Telegram early alert template | notifications | Yes |

### Part 11 — Strategy + Risk
| Module | Path | MVP |
|--------|------|-----|
| Setup classification A–D | `strategy/` | Yes |
| Entry / Stop / TP / RR | same | Yes |
| Position size + leverage caps + liquidity risk | same | Yes |
| Trade plan DB + API | models + `/trade-plan` | Yes |
| Lifecycle / trailing / auto-exec | — | Later |

### Part 12 — Trading Terminal
| Module | Path | MVP |
|--------|------|-----|
| Terminal page: chart + zones + AI + plan | `/terminal` | Yes |
| Watchlist Hot/Watching/Sleeping | terminal | Yes |
| Manual confirm buttons (UI) | terminal | Yes |
| Encrypted exchange keys / live orders | — | Later |

### Part 13 — ML / Decision
| Module | Path | MVP |
|--------|------|-----|
| Feature engineering vector | `ml/features.py` | Yes |
| Pump / Direction / Risk probability (heuristic MVP) | `ml/models.py` | Yes |
| Decision Engine (ML+SMC+Liquidity) | `ml/decision.py` | Yes |
| Wire to AI explain + hunter | API | Yes |
| XGBoost training pipeline | — | Later (dataset first) |

---

## Part 14 — SaaS Database Architecture

| Module | Path | Status |
|--------|------|--------|
| Full ORM models (users → AI loop) | `database/models.py` | Done |
| Timescale bootstrap + indexes | `connection.init_db`, `docker/init-*.sql` | Done |
| Retention + Redis key map | `database/retention.py`, `redis_cache.py` | Done |
| Market / candidate / training repos | `database/repositories.py` | Done |
| Schema doc | `docs/SCHEMA.md` | Done |
| Alembic versioned migrations | — | Later |
| Per-TF candle retention policies | Timescale jobs | Later |
| Daily backup automation | ops | Later |

**Layers:** PostgreSQL (app) · TimescaleDB (`market_candles`) · Redis (hot path)

**Principle:** Engines write structured rows (events, candidates, signals); AI trains from `training_samples` / `ai_predictions`, not raw exchange dumps.

---

## Parts 15–18 (architecture / UI / backtest / Telegram)

| Spec | MVP status |
|------|------------|
| Microservices tree | Mapped as modules in monolith; RabbitMQ optional (`compose --profile full`) |
| Frontend Command Center (RU) | Dashboard, Scanner, Hunter, Terminal, Positions, Journal, Assistant, Alerts, Replay stub |
| Backtest fees/slippage/Sharpe | Done; walk-forward / Monte Carlo — Later |
| Telegram RU + /scan /positions /risk + CHART/PLAN | Done; Mini App / live TG trade — Later |
| Locale | Site + Telegram + AI → Russian |

---

## Market Universe Engine v2 (replaces Bybit TOP50-only)

```
6 Exchanges → ALL USDT Perps (L1)
     ↓
Cheap Filter: volume tiers / spread / liquidity / new listings (L2)
     ↓
SMC + Derivatives + AI Ranking (L3, 50–100)
     ↓
Trade ideas 5–15  +  Cross-Exchange gaps
```

| Module | Path |
|--------|------|
| Collector L1 | `universe/collector.py` |
| Cheap filter L2 | `universe/cheap_filter.py` |
| Heavy L3 | `universe/heavy.py` |
| Cross-exchange | `universe/cross_exchange.py` |
| Orchestrator | `universe/engine.py` |
| API | `POST /api/v1/universe/run`, `GET /universe/snapshot|ideas|cross` |
| Celery | `universe_scan` every 5 min (L1+L2; heavy optional) |

**Tiers:** A 500k–20M · B 100k–500k · C new &lt;30d · exclude BTC/ETH/SOL majors

---

## Entry Assistant (момент входа)

| Status | Meaning |
|--------|---------|
| WATCH | Интересно, ждём |
| SETUP_FORMING | Сетап собирается |
| APPROACHING_ENTRY | Подход к зоне |
| ENTRY_READY | Зона + триггеры режима |
| MISSED | Опоздали |
| INVALIDATED | Сценарий сломан |

Modes: `conservative` (sweep+CHoCH+vol) · `balanced` (sweep+BOS+FVG+OI) · `aggressive` (compression/anomaly + AI≥90)

API: `POST /api/v1/entry/evaluate` · UI: Terminal → **AI Entry Assistant**

---

## Signal Card v3 (обязательно)

Карточка отвечает: **открывать сейчас / ждать / уже поздно / сценарий мёртв?**

### Два независимых рейтинга (без скрытой «готовности»)

| Score | UI | Смысл |
|-------|-----|--------|
| **Structure / Setup** | число + ★★★★☆ | Качество SMC |
| **Execution** | число + ☆☆☆☆☆ | Готовность к входу |

Опционально: `Overall = Setup×70% + Execution×30%` (формула открыта).

### Блоки карточки

1. Symbol + LONG/SHORT + Status  
2. Market Phase — Accumulation / Distribution / Markup / Markdown  
3. Structure Score + Execution Score (звёзды)  
4. Current / Entry / Distance %  
5. Confirmed ✅  
6. Waiting For □ (Volume Spike, OI, Entry Zone, Order Flow)  
7. Zone note (понятное объяснение Premium/Discount)  
8. Trade Plan + Scenario Risk %  
9. AI Conclusion (1–2 предложения)  
10. **Action** — WAIT / ENTER / CANCEL  
11. Таймер: возраст · актуальность · автопереоценка 60с  

### Lifecycle (сопровождение)

WATCH → SETUP_FORMING → ENTRY_ZONE → ENTRY_READY → IN_POSITION → TP1_HIT → TP2_HIT → INVALIDATED  

**Code:** `engines/scoring/readiness.py` · `SignalCard.tsx` · `signal_serialize.py`
