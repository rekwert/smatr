"""Trade simulator (Part 6 / 17) — entry, fees, slippage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Sequence

from app.market_data.candles import CandleBar

EntryModel = Literal["aggressive", "conservative", "limit"]

# MVP fee table (taker %), Part 17 §9
EXCHANGE_FEES = {
    "bybit": 0.00055,
    "okx": 0.0005,
    "bitget": 0.0006,
    "mexc": 0.0006,
    "bingx": 0.0005,
    "kucoin": 0.0006,
}


@dataclass(slots=True)
class SimulatedTrade:
    result: str  # WIN | LOSS | OPEN
    rr: float
    bars_held: int
    time_in_trade: str
    exit_price: Optional[float]
    entry_price: float
    stop: float
    target: float
    fees_r: float = 0.0
    slippage_pct: float = 0.0


def estimate_slippage_pct(notional: float = 10_000, volume_24h: float = 5_000_000) -> float:
    """Rough liquidity impact for low-cap coins."""
    if volume_24h <= 0:
        return 0.02
    impact = min(0.03, (notional / volume_24h) * 2.5)
    return round(impact, 5)


def simulate_trade(
    candles: Sequence[CandleBar],
    entry: float,
    stop: float,
    target: float,
    direction: str = "LONG",
    entry_model: EntryModel = "aggressive",
    start_index: int = 0,
    timeframe_minutes: int = 15,
    exchange: str = "bybit",
    notional: float = 10_000,
    volume_24h: float = 5_000_000,
    apply_costs: bool = True,
) -> SimulatedTrade:
    if not candles or start_index >= len(candles):
        return SimulatedTrade("OPEN", 0, 0, "0h", None, entry, stop, target)

    i = start_index
    if entry_model == "conservative":
        i = min(start_index + 1, len(candles) - 1)
    fill = entry
    if entry_model == "limit":
        fill = (entry + stop) / 2

    slip = estimate_slippage_pct(notional, volume_24h) if apply_costs else 0.0
    fee = EXCHANGE_FEES.get(exchange.lower(), 0.00055) if apply_costs else 0.0
    if direction.upper() == "LONG":
        fill = fill * (1 + slip)
    else:
        fill = fill * (1 - slip)

    risk = abs(fill - stop) or 1e-9
    # Round-trip fee in R units
    fees_r = (2 * fee * fill) / risk if apply_costs else 0.0

    for j in range(i, len(candles)):
        c = candles[j]
        if direction.upper() == "LONG":
            hit_stop = c.low <= stop
            hit_tp = c.high >= target
            if hit_stop and hit_tp:
                bars = j - i
                return SimulatedTrade(
                    "LOSS", -1.0 - fees_r, bars, _fmt_time(bars, timeframe_minutes), stop, fill, stop, target, fees_r, slip
                )
            if hit_stop:
                bars = j - i
                return SimulatedTrade(
                    "LOSS", -1.0 - fees_r, bars, _fmt_time(bars, timeframe_minutes), stop, fill, stop, target, fees_r, slip
                )
            if hit_tp:
                bars = j - i
                rr = abs(target - fill) / risk - fees_r
                return SimulatedTrade(
                    "WIN", rr, bars, _fmt_time(bars, timeframe_minutes), target, fill, stop, target, fees_r, slip
                )
        else:
            hit_stop = c.high >= stop
            hit_tp = c.low <= target
            if hit_stop and hit_tp:
                bars = j - i
                return SimulatedTrade(
                    "LOSS", -1.0 - fees_r, bars, _fmt_time(bars, timeframe_minutes), stop, fill, stop, target, fees_r, slip
                )
            if hit_stop:
                bars = j - i
                return SimulatedTrade(
                    "LOSS", -1.0 - fees_r, bars, _fmt_time(bars, timeframe_minutes), stop, fill, stop, target, fees_r, slip
                )
            if hit_tp:
                bars = j - i
                rr = abs(fill - target) / risk - fees_r
                return SimulatedTrade(
                    "WIN", rr, bars, _fmt_time(bars, timeframe_minutes), target, fill, stop, target, fees_r, slip
                )

    return SimulatedTrade(
        "OPEN", 0.0, len(candles) - i, _fmt_time(len(candles) - i, timeframe_minutes), None, fill, stop, target, fees_r, slip
    )


def _fmt_time(bars: int, tf_min: int) -> str:
    hours = (bars * tf_min) / 60
    if hours < 1:
        return f"{int(bars * tf_min)}m"
    return f"{hours:.1f}h"
