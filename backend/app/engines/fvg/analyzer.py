"""Fair Value Gap Engine (Part 2 §6)."""

from __future__ import annotations

from typing import Sequence

from app.engines.types import EngineEvent
from app.market_data.candles import CandleBar


class FVGAnalyzer:
    def detect(self, candles: Sequence[CandleBar], lookback: int = 80) -> list[EngineEvent]:
        events: list[EngineEvent] = []
        start = max(2, len(candles) - lookback)
        for i in range(start, len(candles)):
            c1, c2, c3 = candles[i - 2], candles[i - 1], candles[i]
            # Bullish FVG: low of c3 > high of c1
            if c3.low > c1.high:
                top, bottom = c3.low, c1.high
                size = top - bottom
                score = self.calculate_quality(c1, c2, c3, size, bullish=True)
                mitigated = any(c.low <= bottom for c in candles[i + 1 :]) if i + 1 < len(candles) else False
                events.append(
                    EngineEvent(
                        type="bullish_fvg",
                        direction="bullish",
                        strength=score,
                        top=top,
                        bottom=bottom,
                        price=(top + bottom) / 2,
                        index=i - 1,
                        metadata={
                            "size": size,
                            "status": "mitigated" if mitigated else "open",
                            "impulse_body": c2.body,
                            "timestamp": c2.timestamp,
                        },
                    )
                )
            # Bearish FVG: high of c3 < low of c1
            if c3.high < c1.low:
                top, bottom = c1.low, c3.high
                size = top - bottom
                score = self.calculate_quality(c1, c2, c3, size, bullish=False)
                mitigated = any(c.high >= top for c in candles[i + 1 :]) if i + 1 < len(candles) else False
                events.append(
                    EngineEvent(
                        type="bearish_fvg",
                        direction="bearish",
                        strength=score,
                        top=top,
                        bottom=bottom,
                        price=(top + bottom) / 2,
                        index=i - 1,
                        metadata={
                            "size": size,
                            "status": "mitigated" if mitigated else "open",
                            "impulse_body": c2.body,
                            "timestamp": c2.timestamp,
                        },
                    )
                )
        # Keep open + strongest recent
        open_events = [e for e in events if e.metadata.get("status") == "open"]
        open_events.sort(key=lambda e: (e.index or 0, e.strength), reverse=True)
        return open_events[:5]

    def detect_bullish_fvg(self, candles: Sequence[CandleBar]) -> list[EngineEvent]:
        return [e for e in self.detect(candles) if e.type == "bullish_fvg"]

    def detect_bearish_fvg(self, candles: Sequence[CandleBar]) -> list[EngineEvent]:
        return [e for e in self.detect(candles) if e.type == "bearish_fvg"]

    @staticmethod
    def calculate_quality(
        c1: CandleBar,
        c2: CandleBar,
        c3: CandleBar,
        size: float,
        bullish: bool,
    ) -> float:
        impulse = c2.body
        vol = c2.volume
        avg_range = (c1.range + c2.range + c3.range) / 3 or 1e-9
        size_score = min(40.0, (size / avg_range) * 25)
        impulse_score = min(30.0, (impulse / avg_range) * 20)
        volume_score = 15.0 if vol > 0 else 0.0
        structure_bonus = 15.0 if (bullish and c2.bullish) or (not bullish and c2.bearish) else 5.0
        return min(100.0, size_score + impulse_score + volume_score + structure_bonus)
