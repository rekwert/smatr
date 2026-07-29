"""Candle normalizer utilities."""

from __future__ import annotations

from typing import Any, Sequence

from app.exchange_layer.base.models import UnifiedCandle
from app.exchange_layer.normalizer.symbols import normalize_symbol, to_canonical_tf
from app.market_data.validation import validate_candle


def normalize_candle_row(
    exchange: str,
    symbol: str,
    timeframe: str,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float,
    timestamp_ms: int,
) -> UnifiedCandle | None:
    candle = UnifiedCandle(
        exchange=exchange.lower(),
        symbol=normalize_symbol(symbol),
        timeframe=to_canonical_tf(timeframe),
        open=float(open_),
        high=float(high),
        low=float(low),
        close=float(close),
        volume=float(volume),
        timestamp=int(timestamp_ms),
        type="future",
    )
    ok, _ = validate_candle(candle.to_bar())
    return candle if ok else None


def candles_to_unified_list(items: Sequence[UnifiedCandle]) -> list[dict[str, Any]]:
    return [c.to_dict() for c in items]
