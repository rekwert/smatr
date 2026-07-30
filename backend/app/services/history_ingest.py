"""Durable market history ingest → Timescale market_candles + derivatives_data."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.models import DerivativesData, MarketCandle, Signal
from app.database.repositories import upsert_market_candles
from app.exchange_layer.connectors import DEFAULT_EXCHANGES
from app.exchange_layer.market_data_engine import MarketDataEngine
from app.market_data.candles import CandleBar
from app.market_data.validation import filter_valid

logger = logging.getLogger(__name__)


async def store_bars(
    db: AsyncSession,
    bars: Sequence[CandleBar],
    *,
    exchange: str,
    symbol: str,
    timeframe: str,
) -> int:
    """Persist OHLCV into market_candles (idempotent upsert)."""
    clean = filter_valid(list(bars))
    if not clean:
        return 0
    return await upsert_market_candles(
        db,
        clean,
        exchange=exchange.lower(),
        symbol=symbol.upper(),
        timeframe=timeframe,
    )


async def store_derivatives(
    db: AsyncSession,
    *,
    exchange: str,
    symbol: str,
    open_interest: Optional[float] = None,
    funding_rate: Optional[float] = None,
    timestamp_ms: Optional[int] = None,
) -> None:
    if open_interest is None and funding_rate is None:
        return
    db.add(
        DerivativesData(
            exchange=exchange.lower(),
            symbol=symbol.upper(),
            open_interest=open_interest,
            funding_rate=funding_rate,
            timestamp=timestamp_ms or int(time.time() * 1000),
        )
    )
    await db.commit()


async def persist_signal_row(db: AsyncSession, row: dict[str, Any]) -> Optional[Signal]:
    """Write / refresh an active signal from memory/universe payload into Postgres."""
    score = int(row.get("score") or row.get("setup_score") or 0)
    if score < settings.min_signal_score:
        return None

    symbol = str(row["symbol"]).upper()
    exchange = str(row.get("exchange") or "bybit").lower()
    timeframe = str(row.get("timeframe") or "15")

    from sqlalchemy import delete

    await db.execute(
        delete(Signal).where(
            Signal.symbol == symbol,
            Signal.exchange == exchange,
            Signal.timeframe == timeframe,
            Signal.status == "active",
        )
    )

    reason = dict(row.get("reason") or {})
    # Keep analyzable history inside JSONB reason
    for key in (
        "setup_score",
        "execution_score",
        "overall_score",
        "probability",
        "scenario_probability",
        "entry_probability_now",
        "lifecycle_status",
        "timing",
        "edge_score",
        "edge_reasons",
        "score_history",
        "replay",
        "components",
        "universe_v2",
        "ai_conclusion",
        "waiting_for",
        "feed",
        "checklist",
    ):
        if row.get(key) is not None:
            reason[key] = row.get(key)
    reason.setdefault("feed", row.get("feed") or "inefficiency")

    signal = Signal(
        symbol=symbol,
        exchange=exchange,
        direction=row.get("direction") or "LONG",
        signal_type=row.get("signal_type") or "smc",
        score=score,
        confidence=row.get("confidence") or "medium",
        timeframe=timeframe,
        entry=row.get("entry") or row.get("ideal_entry"),
        stop=row.get("stop"),
        target=row.get("target") or row.get("tp2"),
        risk_reward=row.get("risk_reward"),
        risk_pct=row.get("risk_pct"),
        reason=reason,
        zones=row.get("zones") or {},
        explanation=row.get("explanation") or row.get("ai_conclusion"),
        status="active",
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    return signal


async def ingest_top_history(
    db: AsyncSession,
    *,
    exchanges: Optional[list[str]] = None,
    per_exchange: int = 15,
    timeframes: Optional[list[str]] = None,
    candle_limit: int = 200,
) -> dict[str, Any]:
    """
    Pull top-volume symbols per exchange and upsert candles + OI/funding.
    Designed for Celery beat / manual bootstrap.
    """
    names = exchanges or settings.exchange_list or list(DEFAULT_EXCHANGES)
    tfs = timeframes or ["15", "60"]
    mde = MarketDataEngine(names)

    candles_written = 0
    oi_written = 0
    errors: list[str] = []
    symbols_seen: list[str] = []

    for ex in names:
        try:
            adapter = mde.get_adapter(ex)
            tickers = await adapter.get_tickers()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{ex}:tickers:{exc}")
            logger.warning("history ingest tickers failed %s: %s", ex, exc)
            continue

        ranked = sorted(
            [t for t in tickers if str(getattr(t, "symbol", "") or "").upper().endswith("USDT")],
            key=lambda t: float(getattr(t, "volume_24h", 0) or 0),
            reverse=True,
        )[:per_exchange]

        for t in ranked:
            sym = str(t.symbol).upper().replace("-", "").replace("_", "")
            if sym.endswith("USDTUSDT"):
                sym = sym.replace("USDTUSDT", "USDT")
            # normalize common suffixes already handled by adapter usually
            from app.exchange_layer.normalizer.symbols import normalize_symbol

            sym = normalize_symbol(sym)
            symbols_seen.append(f"{ex}:{sym}")

            for tf in tfs:
                try:
                    bars = await mde.get_candles_as_bars(
                        sym, tf, exchange=ex, limit=candle_limit
                    )
                    n = await store_bars(db, bars, exchange=ex, symbol=sym, timeframe=tf)
                    candles_written += n
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{ex}:{sym}:{tf}:{exc}")
                    logger.debug("candle ingest fail %s/%s/%s: %s", ex, sym, tf, exc)

            try:
                oi = await adapter.get_open_interest(sym)
                funding = None
                try:
                    funding = await adapter.get_funding_rate(sym)
                except Exception:  # noqa: BLE001
                    funding = getattr(t, "funding_rate", None)
                oi_val = None
                if isinstance(oi, dict):
                    oi_val = float(oi.get("open_interest") or oi.get("oi") or 0) or None
                elif isinstance(oi, (int, float)):
                    oi_val = float(oi)
                fund_val = float(funding) if funding is not None else getattr(t, "funding_rate", None)
                if oi_val is not None or fund_val is not None:
                    await store_derivatives(
                        db,
                        exchange=ex,
                        symbol=sym,
                        open_interest=oi_val,
                        funding_rate=float(fund_val) if fund_val is not None else None,
                    )
                    oi_written += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{ex}:{sym}:oi:{exc}")

    return {
        "exchanges": names,
        "symbols": len(symbols_seen),
        "candles_written": candles_written,
        "derivatives_written": oi_written,
        "errors": errors[:20],
        "error_count": len(errors),
    }
