"""Order Block Engine (Part 2 §7) + Premium/Discount (Part 2 §8)."""

from __future__ import annotations

from typing import Optional, Sequence

from app.engines.structure.analyzer import StructureAnalyzer
from app.engines.types import EngineEvent
from app.market_data.candles import CandleBar


class OrderBlockAnalyzer:
    def __init__(self, swing_length: int = 3):
        self.structure = StructureAnalyzer(swing_length=swing_length)

    def find_bullish_ob(
        self,
        candles: Sequence[CandleBar],
        bos_events: Optional[Sequence[EngineEvent]] = None,
    ) -> list[EngineEvent]:
        bos_events = list(bos_events) if bos_events is not None else self.structure.detect_bos(candles)
        bullish_bos = [b for b in bos_events if b.direction == "bullish"]
        events: list[EngineEvent] = []

        for bos in bullish_bos:
            idx = bos.index or 0
            # Last bearish candle before impulse/BOS
            for j in range(idx - 1, max(-1, idx - 12), -1):
                c = candles[j]
                if c.bearish:
                    strength = min(100.0, 55 + bos.strength * 0.35)
                    events.append(
                        EngineEvent(
                            type="bullish_order_block",
                            direction="bullish",
                            strength=strength,
                            top=c.high,
                            bottom=c.low,
                            price=(c.high + c.low) / 2,
                            index=j,
                            metadata={"bos_index": idx, "timestamp": c.timestamp},
                        )
                    )
                    break
        return events[-3:]

    def find_bearish_ob(
        self,
        candles: Sequence[CandleBar],
        bos_events: Optional[Sequence[EngineEvent]] = None,
    ) -> list[EngineEvent]:
        bos_events = list(bos_events) if bos_events is not None else self.structure.detect_bos(candles)
        bearish_bos = [b for b in bos_events if b.direction == "bearish"]
        events: list[EngineEvent] = []

        for bos in bearish_bos:
            idx = bos.index or 0
            for j in range(idx - 1, max(-1, idx - 12), -1):
                c = candles[j]
                if c.bullish:
                    strength = min(100.0, 55 + bos.strength * 0.35)
                    events.append(
                        EngineEvent(
                            type="bearish_order_block",
                            direction="bearish",
                            strength=strength,
                            top=c.high,
                            bottom=c.low,
                            price=(c.high + c.low) / 2,
                            index=j,
                            metadata={"bos_index": idx, "timestamp": c.timestamp},
                        )
                    )
                    break
        return events[-3:]


class PremiumDiscountAnalyzer:
    def analyze(self, candles: Sequence[CandleBar], lookback: int = 50) -> dict:
        window = candles[-lookback:] if len(candles) >= lookback else list(candles)
        if not window:
            return {"zone": "unknown", "high": None, "low": None, "mid": None}

        high = max(c.high for c in window)
        low = min(c.low for c in window)
        mid = (high + low) / 2
        price = window[-1].close
        if price >= mid:
            zone = "premium"
        else:
            zone = "discount"
        return {
            "zone": zone,
            "high": high,
            "low": low,
            "mid": mid,
            "price": price,
            "long_preferred": zone == "discount",
            "short_preferred": zone == "premium",
        }
