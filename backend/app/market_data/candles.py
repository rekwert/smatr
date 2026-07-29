from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(slots=True)
class CandleBar:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def bullish(self) -> bool:
        return self.close >= self.open

    @property
    def bearish(self) -> bool:
        return self.close < self.open

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return self.high - self.low


def to_arrays(candles: Sequence[CandleBar]) -> dict[str, np.ndarray]:
    return {
        "ts": np.array([c.timestamp for c in candles], dtype=np.int64),
        "o": np.array([c.open for c in candles], dtype=np.float64),
        "h": np.array([c.high for c in candles], dtype=np.float64),
        "l": np.array([c.low for c in candles], dtype=np.float64),
        "c": np.array([c.close for c in candles], dtype=np.float64),
        "v": np.array([c.volume for c in candles], dtype=np.float64),
    }


def atr(candles: Sequence[CandleBar], period: int = 14) -> float:
    if len(candles) < period + 1:
        if not candles:
            return 0.0
        ranges = [c.range for c in candles]
        return float(np.mean(ranges)) if ranges else 0.0

    trs: list[float] = []
    for i in range(1, len(candles)):
        c = candles[i]
        prev = candles[i - 1]
        tr = max(c.high - c.low, abs(c.high - prev.close), abs(c.low - prev.close))
        trs.append(tr)
    window = trs[-period:]
    return float(np.mean(window)) if window else 0.0
