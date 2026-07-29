"""Market regime detector (Part 7 §14)."""

from __future__ import annotations

from typing import Sequence

from app.engines.structure.analyzer import StructureAnalyzer
from app.market_data.candles import CandleBar, atr


class MarketRegimeDetector:
    def __init__(self):
        self.structure = StructureAnalyzer()

    def analyze(self, candles: Sequence[CandleBar]) -> dict:
        if len(candles) < 30:
            return {"market_regime": "unknown", "confidence": 0, "details": {}}

        swings = self.structure.find_swings(candles)
        trend = self.structure.current_trend(swings)
        current_atr = atr(candles, 14)
        avg_atr = atr(candles[:-14] if len(candles) > 28 else candles, 14) or 1e-9
        atr_ratio = current_atr / avg_atr

        vols = [c.volume for c in candles[-24:]]
        early = sum(vols[:8]) / 8 if len(vols) >= 8 else sum(vols) / len(vols)
        late = sum(vols[-8:]) / 8 if len(vols) >= 8 else early
        vol_rise = late / early if early else 1.0

        window = candles[-30:]
        hi = max(c.high for c in window)
        lo = min(c.low for c in window)
        range_pct = (hi - lo) / (window[-1].close or 1e-9) * 100

        if atr_ratio >= 1.6 and vol_rise >= 1.4:
            regime, conf = "expansion", 85
        elif atr_ratio <= 0.55 and vol_rise >= 1.2 and range_pct < 6:
            regime, conf = "accumulation", 87
        elif trend in ("bullish", "bearish") and atr_ratio >= 0.9:
            regime, conf = "trending", 80
        elif range_pct < 5 and atr_ratio < 0.9:
            regime, conf = "ranging", 75
        else:
            regime, conf = "ranging" if trend == "range" else "trending", 55

        return {
            "market_regime": regime,
            "confidence": conf,
            "details": {
                "structure_trend": trend,
                "atr_ratio": round(atr_ratio, 3),
                "volume_rise": round(vol_rise, 2),
                "range_pct": round(range_pct, 2),
            },
        }
