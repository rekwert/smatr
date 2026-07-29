from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException, Query

from app.exchanges.bybit import BybitClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/charts", tags=["charts"])

_INVALID_SYM = re.compile(r"Symbol Is Invalid|symbol.?invalid|not.?found", re.I)


@router.get("/{symbol}")
async def chart_data(
    symbol: str,
    timeframe: str = Query("15"),
    limit: int = Query(200, ge=20, le=1000),
    exchange: str = Query("bybit"),
):
    """OHLCV for Lightweight Charts — всегда с Bybit (без зависимости от Postgres)."""
    symbol = symbol.upper().strip()
    try:
        client = BybitClient()
        bars = await client.get_klines(symbol, timeframe=timeframe, limit=limit)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if _INVALID_SYM.search(msg) or "10001" in msg:
            logger.warning("Invalid chart symbol %s: %s", symbol, msg)
            raise HTTPException(404, detail=f"Символ {symbol} недоступен на Bybit") from exc
        logger.warning("Bybit klines failed for %s: %s", symbol, msg)
        raise HTTPException(503, detail=f"Не удалось загрузить свечи: {exc}") from exc

    if not bars:
        raise HTTPException(404, detail=f"Нет свечей для {symbol}")

    candles = [
        {
            "time": int(b.timestamp // 1000),
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": float(b.volume),
        }
        for b in bars
    ]
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "exchange": exchange,
        "candles": candles,
        "source": "bybit",
    }
