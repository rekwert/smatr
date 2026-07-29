"""Liquidity Engine — equal highs/lows + sweeps (Part 2 §5)."""

from __future__ import annotations

from typing import Optional, Sequence

from app.config.constants import (
    EQUAL_LEVEL_THRESHOLD_PCT,
    LIQUIDITY_SWEEP_MIN_PIERCE_PCT,
)
from app.engines.structure.analyzer import StructureAnalyzer
from app.engines.types import EngineEvent
from app.market_data.candles import CandleBar


class LiquidityAnalyzer:
    def __init__(
        self,
        equal_threshold_pct: float = EQUAL_LEVEL_THRESHOLD_PCT,
        sweep_pierce_pct: float = LIQUIDITY_SWEEP_MIN_PIERCE_PCT,
        swing_length: int = 3,
    ):
        self.equal_threshold_pct = equal_threshold_pct
        self.sweep_pierce_pct = sweep_pierce_pct
        self.structure = StructureAnalyzer(swing_length=swing_length)

    def find_equal_highs(self, candles: Sequence[CandleBar]) -> list[EngineEvent]:
        swings = [s for s in self.structure.find_swings(candles) if s.type == "swing_high"]
        return self._find_equals(swings, "equal_high", candles)

    def find_equal_lows(self, candles: Sequence[CandleBar]) -> list[EngineEvent]:
        swings = [s for s in self.structure.find_swings(candles) if s.type == "swing_low"]
        return self._find_equals(swings, "equal_low", candles)

    def _find_equals(
        self,
        swings: Sequence[EngineEvent],
        event_type: str,
        candles: Sequence[CandleBar],
    ) -> list[EngineEvent]:
        events: list[EngineEvent] = []
        used: set[int] = set()
        for i in range(len(swings)):
            if i in used or swings[i].price is None:
                continue
            cluster = [swings[i]]
            for j in range(i + 1, len(swings)):
                if j in used or swings[j].price is None:
                    continue
                p1 = swings[i].price or 0
                p2 = swings[j].price or 0
                mid = (p1 + p2) / 2 or 1e-9
                if abs(p1 - p2) / mid * 100 <= self.equal_threshold_pct:
                    cluster.append(swings[j])
                    used.add(j)
            if len(cluster) >= 2:
                used.add(i)
                price = sum(c.price or 0 for c in cluster) / len(cluster)
                touches = len(cluster)
                # crude time visible via index span
                idxs = [c.index or 0 for c in cluster]
                span = max(idxs) - min(idxs)
                strength = min(100.0, 40 + touches * 15 + min(span, 40) * 0.5)
                events.append(
                    EngineEvent(
                        type=event_type,
                        direction="bearish" if "high" in event_type else "bullish",
                        strength=strength,
                        price=price,
                        index=max(idxs),
                        metadata={"touches": touches, "span": span},
                    )
                )
        return events

    def detect_sweep(
        self,
        candles: Sequence[CandleBar],
        swings: Optional[Sequence[EngineEvent]] = None,
    ) -> list[EngineEvent]:
        swings = list(swings) if swings is not None else self.structure.find_swings(candles)
        if len(candles) < 5:
            return []

        avg_vol = sum(c.volume for c in candles[-20:]) / max(1, min(20, len(candles)))
        events: list[EngineEvent] = []

        for i in range(2, len(candles)):
            candle = candles[i]
            prior = [s for s in swings if (s.index or 0) < i - 1]
            last_low = next((s for s in reversed(prior) if s.type == "swing_low"), None)
            last_high = next((s for s in reversed(prior) if s.type == "swing_high"), None)

            # Bullish sweep: pierce below swing low, close back above
            if last_low and last_low.price:
                level = last_low.price
                pierce_pct = (level - candle.low) / level * 100 if level else 0
                if (
                    candle.low < level
                    and pierce_pct >= self.sweep_pierce_pct
                    and candle.close > level
                ):
                    vol_ok = candle.volume >= avg_vol * 1.1 if avg_vol else True
                    strength = min(100.0, 60 + pierce_pct * 20 + (10 if vol_ok else 0))
                    events.append(
                        EngineEvent(
                            type="liquidity_sweep",
                            direction="bullish",
                            strength=strength,
                            price=level,
                            index=i,
                            metadata={
                                "pierce_pct": round(pierce_pct, 4),
                                "volume_confirmed": vol_ok,
                                "timestamp": candle.timestamp,
                            },
                        )
                    )

            # Bearish sweep
            if last_high and last_high.price:
                level = last_high.price
                pierce_pct = (candle.high - level) / level * 100 if level else 0
                if (
                    candle.high > level
                    and pierce_pct >= self.sweep_pierce_pct
                    and candle.close < level
                ):
                    vol_ok = candle.volume >= avg_vol * 1.1 if avg_vol else True
                    strength = min(100.0, 60 + pierce_pct * 20 + (10 if vol_ok else 0))
                    events.append(
                        EngineEvent(
                            type="liquidity_sweep",
                            direction="bearish",
                            strength=strength,
                            price=level,
                            index=i,
                            metadata={
                                "pierce_pct": round(pierce_pct, 4),
                                "volume_confirmed": vol_ok,
                                "timestamp": candle.timestamp,
                            },
                        )
                    )

        # Prefer most recent sweep
        if not events:
            return []
        latest = max(events, key=lambda e: e.index or 0)
        return [latest]
