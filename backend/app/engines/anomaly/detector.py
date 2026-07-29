"""Anomaly detector (Part 7 §19)."""

from __future__ import annotations

from typing import Optional, Sequence

from app.market_data.candles import CandleBar
from app.market_data.volume_intelligence import relative_volume_smart


class AnomalyDetector:
    def analyze(
        self,
        candles: Sequence[CandleBar],
        orderbook_imbalance: Optional[float] = None,
        oi_change_pct: float = 0.0,
    ) -> dict:
        if len(candles) < 10:
            return {"anomaly_score": 0, "reason": [], "is_anomaly": False}

        reasons: list[str] = []
        score = 0.0

        last = candles[-1]
        prev = candles[-6] if len(candles) >= 6 else candles[0]
        move_pct = abs(last.close - prev.close) / (prev.close or 1e-9) * 100
        if move_pct >= 15:
            reasons.append("Price acceleration")
            score += 40
        elif move_pct >= 8:
            reasons.append("Elevated price move")
            score += 20

        vol = relative_volume_smart(candles)
        if vol["rv"] >= 20:
            reasons.append("Volume explosion")
            score += 40
        elif vol["rv"] >= 8:
            reasons.append("Volume spike")
            score += 25
        elif vol["rv"] >= 5:
            reasons.append("High relative volume")
            score += 15

        if abs(oi_change_pct) >= 20:
            reasons.append(f"OI change {oi_change_pct:+.1f}%")
            score += 15

        if orderbook_imbalance is not None and abs(orderbook_imbalance) >= 40:
            reasons.append("Liquidity change / book imbalance")
            score += 15

        score = min(100.0, score)
        return {
            "anomaly_score": int(round(score)),
            "reason": reasons,
            "is_anomaly": score >= 60,
            "rv": vol["rv"],
            "move_pct": round(move_pct, 2),
        }
