from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config.settings import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "development",
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def _seed_exchanges(conn) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO exchanges (name, type, api_status)
            SELECT v.name, v.type, 'unknown'
            FROM (VALUES
              ('bybit', 'futures'),
              ('okx', 'futures'),
              ('bitget', 'futures'),
              ('mexc', 'futures'),
              ('bingx', 'futures'),
              ('kucoin', 'futures')
            ) AS v(name, type)
            WHERE NOT EXISTS (SELECT 1 FROM exchanges e WHERE e.name = v.name)
            """
        )
    )


async def _apply_timescale(conn) -> None:
    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
    # Hypertable — ignore if already converted / extension missing features
    await conn.execute(
        text(
            """
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM information_schema.tables WHERE table_name = 'market_candles'
              ) AND NOT EXISTS (
                SELECT 1 FROM timescaledb_information.hypertables
                WHERE hypertable_name = 'market_candles'
              ) THEN
                PERFORM create_hypertable('market_candles', 'time', if_not_exists => TRUE, migrate_data => TRUE);
              END IF;
            EXCEPTION WHEN OTHERS THEN
              RAISE NOTICE 'hypertable: %', SQLERRM;
            END $$;
            """
        )
    )
    for stmt in [
        "CREATE INDEX IF NOT EXISTS idx_market_candles_symbol_tf_time ON market_candles (exchange, symbol, timeframe, time DESC)",
        "CREATE INDEX IF NOT EXISTS idx_market_trades_symbol_ts ON market_trades (exchange, symbol, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_orderbook_symbol_ts ON orderbook_snapshots (exchange, symbol, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_derivatives_symbol_ts ON derivatives_data (exchange, symbol, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_smart_money_events_symbol_ts ON smart_money_events (symbol, event_type, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_candidates_status_score ON candidates (status, pump_score DESC)",
        "CREATE INDEX IF NOT EXISTS idx_training_samples_label ON training_samples (label, created_at DESC)",
    ]:
        try:
            await conn.execute(text(stmt))
        except Exception:  # noqa: BLE001
            pass


async def init_db() -> None:
    import logging

    import app.database.models  # noqa: F401 — register metadata

    log = logging.getLogger(__name__)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await _seed_exchanges(conn)
        except Exception:  # noqa: BLE001
            pass
        try:
            await _apply_timescale(conn)
        except Exception:  # noqa: BLE001
            pass
    log.info("Database schema ready (%d tables)", len(Base.metadata.tables))
