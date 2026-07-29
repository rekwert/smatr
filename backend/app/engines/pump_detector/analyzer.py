"""Early Pump Detection Engine (Part 2 §10)."""

from __future__ import annotations

from typing import Optional, Sequence

from app.config.constants import ATR_COMPRESSION_RATIO, DEFAULT_PUMP_WEIGHTS
from app.engines.volume.analyzer import VolumeAnalyzer
from app.market_data.candles import CandleBar, atr


class PumpDetector:
    def __init__(self, weights: Optional[dict[str, int]] = None):
        self.weights = weights or DEFAULT_PUMP_WEIGHTS
        self.volume = VolumeAnalyzer()

    def analyze(
        self,
        candles: Sequence[CandleBar],
        oi_change_pct: float = 0.0,
        market_cap: Optional[float] = None,
    ) -> dict:
        if len(candles) < 30:
            return {
                "total": 0,
                "components": {},
                "reasons": ["Insufficient candle history"],
                "status": "insufficient_data",
            }

        compression = self._compression_score(candles)
        accumulation = self._accumulation_score(candles)
        vol = self.volume.analyze(candles)
        volume_score = min(100.0, vol["score"] + (10 if vol["spike"] else 0))
        breakout = self._breakout_score(candles)
        oi_score = self._oi_score(oi_change_pct)
        liq_score = min(100.0, accumulation)
        mcap_score = self._mcap_score(market_cap)
        momentum = self._momentum_score(candles)

        components = {
            "compression": compression,
            "volume_increase": volume_score,
            "breakout": breakout,
            "oi_increase": oi_score,
            "liquidity": liq_score,
            "market_cap": mcap_score,
            "momentum": momentum,
            "accumulation": accumulation,
        }

        total = 0.0
        weight_sum = 0.0
        for key, weight in self.weights.items():
            total += components.get(key, 0) * weight
            weight_sum += weight
        score = int(round(total / weight_sum)) if weight_sum else 0

        reasons = []
        if compression >= 70:
            reasons.append(f"ATR compression ({compression:.0f})")
        if accumulation >= 65:
            reasons.append("Accumulation phase")
        if vol["spike"]:
            reasons.append(f"Volume x{vol['rv']}")
        if breakout >= 70:
            reasons.append("Range breakout")
        if oi_change_pct >= 10:
            reasons.append(f"OI {oi_change_pct:+.1f}%")
        if momentum >= 70:
            reasons.append("Momentum building")

        if score >= 85:
            status = "preparing"
        elif score >= 70:
            status = "watch"
        else:
            status = "normal"

        return {
            "total": score,
            "components": {k: round(v, 1) for k, v in components.items()},
            "reasons": reasons,
            "status": status,
            "rv": vol["rv"],
            "oi_change_pct": oi_change_pct,
        }

    def _compression_score(self, candles: Sequence[CandleBar]) -> float:
        current = atr(candles, 14)
        longer = atr(candles[:-14] if len(candles) > 28 else candles, 14) or 1e-9
        ratio = current / longer
        if ratio <= ATR_COMPRESSION_RATIO:
            return min(100.0, 90 + (ATR_COMPRESSION_RATIO - ratio) * 50)
        if ratio <= 0.7:
            return 60 + (0.7 - ratio) * 80
        if ratio <= 1.0:
            return 30 + (1.0 - ratio) * 100
        return max(0.0, 20 - (ratio - 1) * 20)

    def _accumulation_score(self, candles: Sequence[CandleBar]) -> float:
        window = candles[-24:]
        highs = [c.high for c in window]
        lows = [c.low for c in window]
        range_pct = (max(highs) - min(lows)) / (window[-1].close or 1e-9) * 100
        vols = [c.volume for c in window]
        early = sum(vols[:8]) / 8 if len(vols) >= 8 else sum(vols) / len(vols)
        late = sum(vols[-8:]) / 8 if len(vols) >= 8 else early
        vol_rise = (late / early) if early else 1.0

        # Higher lows / flat lows preferred
        low_slope = lows[-1] - lows[0]
        score = 40.0
        if range_pct < 4:
            score += 25
        elif range_pct < 8:
            score += 12
        if vol_rise >= 1.5:
            score += 20
        elif vol_rise >= 1.2:
            score += 10
        if low_slope >= 0:
            score += 15
        return min(100.0, score)

    def _breakout_score(self, candles: Sequence[CandleBar]) -> float:
        window = candles[-20:-1]
        if len(window) < 5:
            return 0.0
        high = max(c.high for c in window)
        low = min(c.low for c in window)
        last = candles[-1]
        vol = self.volume.analyze(candles)
        if last.close > high and last.bullish:
            return min(100.0, 70 + (10 if vol["spike"] else 0) + min(20, vol["rv"] * 2))
        if last.close < low and last.bearish:
            return min(100.0, 55 + (10 if vol["spike"] else 0))
        # near breakout
        if last.high >= high * 0.998:
            return 45.0
        return 15.0

    @staticmethod
    def _oi_score(oi_change_pct: float) -> float:
        if oi_change_pct >= 30:
            return 100.0
        if oi_change_pct >= 15:
            return 80.0
        if oi_change_pct >= 5:
            return 55.0
        if oi_change_pct > 0:
            return 35.0
        return 10.0

    @staticmethod
    def _mcap_score(market_cap: Optional[float]) -> float:
        if market_cap is None:
            return 50.0
        # Prefer mid/small more reactive names for pump detector
        if market_cap < 50_000_000:
            return 85.0
        if market_cap < 200_000_000:
            return 70.0
        if market_cap < 1_000_000_000:
            return 50.0
        return 30.0

    @staticmethod
    def _momentum_score(candles: Sequence[CandleBar]) -> float:
        if len(candles) < 10:
            return 0.0
        c0 = candles[-10].close or 1e-9
        c1 = candles[-1].close
        pct = (c1 - c0) / c0 * 100
        if pct > 3:
            return min(100.0, 60 + pct * 5)
        if pct > 0:
            return 40 + pct * 5
        return max(0.0, 20 + pct)
