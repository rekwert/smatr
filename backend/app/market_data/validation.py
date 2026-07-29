"""Candle validation before persist (Part 7 §7)."""

from __future__ import annotations

from app.market_data.candles import CandleBar


def validate_candle(bar: CandleBar, max_range_pct: float = 50.0) -> tuple[bool, str]:
    if bar.volume < 0:
        return False, "negative_volume"
    if bar.high < max(bar.open, bar.close):
        return False, "high_below_body"
    if bar.low > min(bar.open, bar.close):
        return False, "low_above_body"
    if bar.high < bar.low:
        return False, "high_lt_low"
    mid = (bar.open + bar.close) / 2 or 1e-12
    range_pct = (bar.high - bar.low) / mid * 100
    if range_pct > max_range_pct:
        return False, "range_spike"
    if bar.open <= 0 or bar.close <= 0:
        return False, "non_positive_price"
    return True, "ok"


def filter_valid(candles: list[CandleBar]) -> list[CandleBar]:
    out: list[CandleBar] = []
    for c in candles:
        ok, _ = validate_candle(c)
        if ok:
            out.append(c)
    return out
