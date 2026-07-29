"""Market Structure Engine — swings, BOS, CHoCH (Part 2 §2–4)."""

from __future__ import annotations

from typing import Optional, Sequence

from app.config.constants import SWING_LENGTH_DEFAULT
from app.engines.types import EngineEvent
from app.market_data.candles import CandleBar, atr


class StructureAnalyzer:
    def __init__(self, swing_length: int = SWING_LENGTH_DEFAULT):
        self.swing_length = max(2, swing_length)

    def find_swings(self, candles: Sequence[CandleBar]) -> list[EngineEvent]:
        n = self.swing_length
        events: list[EngineEvent] = []
        if len(candles) < n * 2 + 1:
            return events

        for i in range(n, len(candles) - n):
            window_left = candles[i - n : i]
            window_right = candles[i + 1 : i + n + 1]
            hi = candles[i].high
            lo = candles[i].low

            if all(hi > c.high for c in window_left) and all(hi > c.high for c in window_right):
                events.append(
                    EngineEvent(
                        type="swing_high",
                        direction="bearish",
                        strength=70.0,
                        price=hi,
                        index=i,
                        metadata={"timestamp": candles[i].timestamp},
                    )
                )
            if all(lo < c.low for c in window_left) and all(lo < c.low for c in window_right):
                events.append(
                    EngineEvent(
                        type="swing_low",
                        direction="bullish",
                        strength=70.0,
                        price=lo,
                        index=i,
                        metadata={"timestamp": candles[i].timestamp},
                    )
                )
        return events

    def current_trend(self, swings: Sequence[EngineEvent]) -> str:
        highs = [e for e in swings if e.type == "swing_high"]
        lows = [e for e in swings if e.type == "swing_low"]
        if len(highs) < 2 or len(lows) < 2:
            return "range"

        last_h, prev_h = highs[-1].price or 0, highs[-2].price or 0
        last_l, prev_l = lows[-1].price or 0, lows[-2].price or 0

        hh = last_h > prev_h
        hl = last_l > prev_l
        lh = last_h < prev_h
        ll = last_l < prev_l

        if hh and hl:
            return "bullish"
        if lh and ll:
            return "bearish"
        return "range"

    def detect_bos(
        self,
        candles: Sequence[CandleBar],
        swings: Optional[Sequence[EngineEvent]] = None,
    ) -> list[EngineEvent]:
        swings = list(swings) if swings is not None else self.find_swings(candles)
        if len(candles) < 5 or not swings:
            return []

        atr_val = atr(candles) or 1e-9
        avg_vol = sum(c.volume for c in candles[-20:]) / max(1, min(20, len(candles)))
        events: list[EngineEvent] = []

        for i in range(1, len(candles)):
            candle = candles[i]
            prior_swings = [s for s in swings if (s.index or 0) < i]
            if not prior_swings:
                continue

            last_high = next((s for s in reversed(prior_swings) if s.type == "swing_high"), None)
            last_low = next((s for s in reversed(prior_swings) if s.type == "swing_low"), None)

            if last_high and last_high.price and candle.close > last_high.price:
                distance = candle.close - last_high.price
                vol_factor = (candle.volume / avg_vol) if avg_vol else 1.0
                strength = min(100.0, (distance / atr_val) * 25.0 * min(vol_factor, 3.0))
                events.append(
                    EngineEvent(
                        type="bos",
                        direction="bullish",
                        strength=strength,
                        price=last_high.price,
                        index=i,
                        metadata={
                            "close": candle.close,
                            "volume_factor": round(vol_factor, 2),
                            "timestamp": candle.timestamp,
                        },
                    )
                )

            if last_low and last_low.price and candle.close < last_low.price:
                distance = last_low.price - candle.close
                vol_factor = (candle.volume / avg_vol) if avg_vol else 1.0
                strength = min(100.0, (distance / atr_val) * 25.0 * min(vol_factor, 3.0))
                events.append(
                    EngineEvent(
                        type="bos",
                        direction="bearish",
                        strength=strength,
                        price=last_low.price,
                        index=i,
                        metadata={
                            "close": candle.close,
                            "volume_factor": round(vol_factor, 2),
                            "timestamp": candle.timestamp,
                        },
                    )
                )

        # Keep latest meaningful BOS per direction to avoid spam
        return self._latest_by_direction(events)

    def detect_choch(
        self,
        candles: Sequence[CandleBar],
        swings: Optional[Sequence[EngineEvent]] = None,
    ) -> list[EngineEvent]:
        swings = list(swings) if swings is not None else self.find_swings(candles)
        trend = self.current_trend(swings)
        bos_list = self.detect_bos(candles, swings)
        events: list[EngineEvent] = []

        for bos in bos_list:
            # CHoCH = structure break against prior trend
            if trend == "bearish" and bos.direction == "bullish":
                events.append(
                    EngineEvent(
                        type="choch",
                        direction="bullish",
                        strength=min(100.0, bos.strength + 5),
                        price=bos.price,
                        index=bos.index,
                        metadata={"prior_trend": trend, **bos.metadata},
                    )
                )
            elif trend == "bullish" and bos.direction == "bearish":
                events.append(
                    EngineEvent(
                        type="choch",
                        direction="bearish",
                        strength=min(100.0, bos.strength + 5),
                        price=bos.price,
                        index=bos.index,
                        metadata={"prior_trend": trend, **bos.metadata},
                    )
                )
        return events

    @staticmethod
    def _latest_by_direction(events: list[EngineEvent]) -> list[EngineEvent]:
        latest: dict[str, EngineEvent] = {}
        for e in events:
            key = e.direction or "na"
            prev = latest.get(key)
            if prev is None or (e.index or 0) >= (prev.index or 0):
                latest[key] = e
        return list(latest.values())
