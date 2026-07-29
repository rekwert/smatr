"""Part 9 Multi-Exchange API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.database.connection import SessionLocal
from app.database.models import Exchange, ExchangeSymbol
from app.exchange_layer.connectors import DEFAULT_EXCHANGES, EXCHANGE_REGISTRY
from app.exchange_layer.market_data_engine import MarketDataEngine
from app.exchange_layer.monitoring.health import check_all_exchanges, status_emoji
from app.exchange_layer.scanners import MultiExchangeSymbolScanner
from app.engines.scoring.calculator import ScoreCalculator
from app.engines.pump_detector.analyzer import PumpDetector

router = APIRouter(prefix="/exchanges", tags=["exchanges"])


@router.get("")
async def list_exchanges():
    return {
        "supported": list(EXCHANGE_REGISTRY.keys()),
        "default": DEFAULT_EXCHANGES,
        "priority": {
            name: EXCHANGE_REGISTRY[name]().priority for name in EXCHANGE_REGISTRY
        },
    }


@router.get("/status")
async def exchange_status():
    """Live health check — DB persist optional."""
    results = await check_all_exchanges()
    for row in results:
        row["emoji"] = status_emoji(row.get("status") or "")

    try:
        with __import__("socket").create_connection(("127.0.0.1", 5433), timeout=0.4):
            pg = True
    except OSError:
        pg = False

    if pg:
        try:
            async with SessionLocal() as db:
                for row in results:
                    name = row["exchange"]
                    existing = (
                        await db.execute(select(Exchange).where(Exchange.name == name))
                    ).scalar_one_or_none()
                    if existing is None:
                        existing = Exchange(name=name)
                        db.add(existing)
                    existing.api_status = row.get("status") or "unknown"
                    existing.latency_ms = row.get("latency_ms")
                    existing.last_check_at = datetime.now(timezone.utc)
                await db.commit()
        except Exception:  # noqa: BLE001
            pass

    return {"exchanges": results, "db": "up" if pg else "down"}


@router.get("/universe")
async def universe(
    min_volume: float = Query(1_000_000, ge=0),
    exchanges: Optional[str] = Query(None, description="comma-separated"),
    limit: int = Query(100, ge=1, le=500),
):
    names = [x.strip() for x in exchanges.split(",")] if exchanges else None
    from app.exchange_layer.connectors import create_exchanges

    scanner = MultiExchangeSymbolScanner(create_exchanges(names) if names else None)
    rows = await scanner.scan_universe(min_volume=min_volume)
    return {"count": len(rows), "symbols": rows[:limit]}


@router.get("/lowcap")
async def lowcap(
    min_volume: float = 5_000_000,
    max_volume: float = 200_000_000,
    limit: int = Query(30, ge=1, le=100),
):
    scanner = MultiExchangeSymbolScanner()
    rows = await scanner.low_cap_candidates(
        min_volume=min_volume, max_volume=max_volume, limit=limit
    )
    return {"count": len(rows), "candidates": rows}


@router.get("/new-listings")
async def new_listings(max_age_hours: float = 72, min_volume: float = 1_000_000):
    scanner = MultiExchangeSymbolScanner()
    rows = await scanner.new_listings(max_age_hours=max_age_hours, min_volume=min_volume)
    return {"count": len(rows), "listings": rows}


@router.get("/{exchange}/candles/{symbol}")
async def candles(
    exchange: str,
    symbol: str,
    timeframe: str = "15m",
    limit: int = Query(200, ge=10, le=1000),
):
    engine = MarketDataEngine([exchange])
    data = await engine.get_candles(symbol, timeframe, exchange=exchange, limit=limit)
    return {
        "exchange": exchange,
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "candles": [c.to_dict() for c in data],
    }


@router.get("/{exchange}/analyze/{symbol}")
async def analyze_on_exchange(
    exchange: str,
    symbol: str,
    timeframe: str = "15m",
):
    """Fetch unified market bundle and run SMC + Pump on normalized candles."""
    mde = MarketDataEngine([exchange])
    bundle = await mde.analysis_bundle(symbol, timeframe=timeframe, exchange=exchange)
    bars = bundle["bars"]
    scorer = ScoreCalculator()
    pump = PumpDetector()
    oi_chg = float((bundle.get("open_interest") or {}).get("oi_change_pct") or 0)
    smc = scorer.analyze_symbol(
        symbol.upper(),
        bars,
        timeframe="15",
        oi_change_pct=oi_chg,
        funding=bundle.get("funding_rate"),
    )
    smc["timeframe"] = timeframe
    pump_res = pump.analyze(bars, oi_change_pct=oi_chg)
    return {
        "exchange": exchange,
        "symbol": symbol.upper(),
        "market": {
            "funding_rate": bundle.get("funding_rate"),
            "open_interest": bundle.get("open_interest"),
            "orderbook": bundle.get("orderbook"),
            "candles": len(bars),
        },
        "smc": smc,
        "pump": pump_res,
    }


@router.post("/sync-symbols")
async def sync_symbols(min_volume: float = 1_000_000):
    """Scan universe; persist to Postgres only if available."""
    scanner = MultiExchangeSymbolScanner()
    rows = await scanner.scan_universe(min_volume=min_volume)
    slice_rows = rows[:500]

    try:
        with __import__("socket").create_connection(("127.0.0.1", 5433), timeout=0.4):
            pg = True
    except OSError:
        pg = False

    if not pg:
        return {
            "upserted": 0,
            "scanned": len(slice_rows),
            "storage": "memory",
            "symbols": slice_rows[:50],
        }

    upserted = 0
    try:
        async with SessionLocal() as db:
            for row in slice_rows:
                existing = (
                    await db.execute(
                        select(ExchangeSymbol).where(
                            ExchangeSymbol.exchange == row["exchange"],
                            ExchangeSymbol.symbol == row["symbol"],
                        )
                    )
                ).scalar_one_or_none()
                if existing is None:
                    existing = ExchangeSymbol(
                        exchange=row["exchange"], symbol=row["symbol"]
                    )
                    db.add(existing)
                existing.volume_24h = row["volume24h"]
                existing.liquidity_score = row["liquidity_score"]
                existing.price = row["price"]
                existing.active = True
                existing.meta = {
                    "spread_pct": row.get("spread_pct"),
                    "change_pct_24h": row.get("change_pct_24h"),
                }
                upserted += 1
            await db.commit()
    except Exception:  # noqa: BLE001
        return {
            "upserted": 0,
            "scanned": len(slice_rows),
            "storage": "memory",
            "symbols": slice_rows[:50],
        }

    return {"upserted": upserted, "scanned": len(slice_rows), "storage": "postgres"}
