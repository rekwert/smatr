"""Volume Engine (Part 2 §9)."""

from __future__ import annotations

from typing import Sequence

from app.config.constants import VOLUME_SPIKE_MULTIPLIER
from app.engines.types import EngineEvent
from app.market_data.candles import CandleBar


class VolumeAnalyzer:
    def __init__(self, lookback: int = 20, spike_x: float = VOLUME_SPIKE_MULTIPLIER):
        self.lookback = lookback
        self.spike_x = spike_x

    def relative_volume(self, candles: Sequence[CandleBar]) -> float:
        if not candles:
            return 0.0
        window = candles[-(self.lookback + 1) : -1]
        if not window:
            return 1.0
        avg = sum(c.volume for c in window) / len(window)
        if avg <= 0:
            return 0.0
        return candles[-1].volume / avg

    def analyze(self, candles: Sequence[CandleBar]) -> dict:
        rv = self.relative_volume(candles)
        if rv < 1:
            rating = "weak"
            score = max(0.0, rv * 30)
        elif rv < 2:
            rating = "normal"
            score = 40 + (rv - 1) * 20
        elif rv < 5:
            rating = "elevated"
            score = 60 + (rv - 2) * 8
        else:
            rating = "anomaly"
            score = min(100.0, 85 + (rv - 5) * 2)

        spike = rv >= self.spike_x
        event = None
        if spike:
            event = EngineEvent(
                type="volume_spike",
                direction=None,
                strength=min(100.0, score),
                price=candles[-1].close if candles else None,
                index=len(candles) - 1,
                metadata={"rv": round(rv, 2)},
            )
        return {
            "rv": round(rv, 2),
            "rating": rating,
            "score": round(score, 1),
            "spike": spike,
            "event": event,
        }
