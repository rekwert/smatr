from __future__ import annotations

from app.market_data.candles import CandleBar


def make_candles(pattern: list[tuple[float, float, float, float, float]], start_ts: int = 1_700_000_000_000) -> list[CandleBar]:
    """pattern items: open, high, low, close, volume"""
    out: list[CandleBar] = []
    for i, (o, h, l, c, v) in enumerate(pattern):
        out.append(
            CandleBar(
                timestamp=start_ts + i * 60_000,
                open=o,
                high=h,
                low=l,
                close=c,
                volume=v,
            )
        )
    return out


def trending_up(n: int = 80) -> list[CandleBar]:
    pattern = []
    price = 100.0
    for i in range(n):
        o = price
        # every 8 bars: pullback creating a swing low, else grind up
        if i % 8 == 0 and i > 0:
            c = price - 1.8
            h = o + 0.15
            l = c - 0.35
        elif i % 8 == 4:
            c = price + 1.6
            h = c + 0.4
            l = o - 0.1
        else:
            c = price + 0.35
            h = c + 0.2
            l = o - 0.12
        pattern.append((o, h, l, c, 1000 + i * 10))
        price = c
    return make_candles(pattern)


def liquidity_sweep_bullish() -> list[CandleBar]:
    """Build swings then pierce low and close back above."""
    pattern = []
    # flat-ish with clear swing low around index 10
    for i in range(20):
        pattern.append((100, 101, 99, 100.2, 1000))
    # create swing low
    pattern[10] = (100, 100.5, 95.0, 99.5, 1200)
    # neighbors higher lows
    pattern[7] = (100, 101, 98, 100, 1000)
    pattern[8] = (100, 101, 98.2, 100, 1000)
    pattern[9] = (100, 101, 97.5, 100, 1000)
    pattern[11] = (99.5, 101, 98, 100, 1000)
    pattern[12] = (100, 101, 98.1, 100.1, 1000)
    pattern[13] = (100, 101, 98.3, 100.2, 1000)
    # more bars
    for _ in range(10):
        pattern.append((100.2, 101.2, 99.5, 100.5, 1100))
    # sweep candle
    pattern.append((100.5, 100.8, 94.5, 100.6, 5000))
    return make_candles(pattern)


def fvg_bullish_set() -> list[CandleBar]:
    pattern = []
    for i in range(30):
        pattern.append((100 + i * 0.1, 100.5 + i * 0.1, 99.5 + i * 0.1, 100.2 + i * 0.1, 1000))
    # C1 high, C2 impulse, C3 low > C1 high
    pattern.append((105, 106, 104.5, 105.5, 2000))  # c1
    pattern.append((105.5, 110, 105.4, 109.5, 8000))  # c2 impulse
    pattern.append((109.5, 111, 107.5, 110, 3000))  # c3 low 107.5 > c1 high 106
    return make_candles(pattern)
