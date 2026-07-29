"""Quant AI models — heuristic MVP ready for XGBoost swap (Part 13 §12–13)."""

from __future__ import annotations

from typing import Any


def _sigmoid(x: float) -> float:
    import math

    return 1 / (1 + math.exp(-max(-20, min(20, x))))


def pump_probability(features: dict[str, Any]) -> float:
    """Return 0–1 probability of strong expansion."""
    f = features
    score = (
        f.get("atr_compression", 0) * 2.2
        + min(f.get("volume_ratio", 0) / 8, 1.5) * 1.8
        + f.get("volume_spike", 0) * 0.8
        + f.get("liquidity_sweep", 0) * 0.7
        + f.get("bos", 0) * 0.6
        + min(abs(f.get("oi_change", 0)) / 30, 1.2) * 0.9
        + min(abs(f.get("orderbook_imbalance", 0)) / 50, 1) * 0.4
        + f.get("btc_trend_bullish", 0) * 0.3
        - (0.8 if abs(f.get("chg_5", 0)) > 25 else 0)  # already moved
    )
    return round(_sigmoid(score - 1.2), 4)


def direction_probability(features: dict[str, Any]) -> dict[str, float]:
    long_score = 0.0
    short_score = 0.0
    if features.get("sweep_direction") == "bullish" or features.get("bos_direction") == "bullish":
        long_score += 1.2
    if features.get("sweep_direction") == "bearish" or features.get("bos_direction") == "bearish":
        short_score += 1.2
    if features.get("structure_trend") == "bullish":
        long_score += 0.8
    if features.get("structure_trend") == "bearish":
        short_score += 0.8
    if features.get("chg_5", 0) > 0:
        long_score += 0.3
    else:
        short_score += 0.3
    if features.get("orderbook_imbalance", 0) > 0:
        long_score += 0.4
    else:
        short_score += 0.2
    # softmax-ish
    import math

    el, es = math.exp(long_score), math.exp(short_score)
    s = el + es
    return {"LONG": round(el / s, 4), "SHORT": round(es / s, 4)}


def risk_probability(features: dict[str, Any]) -> dict[str, Any]:
    risk = 0.2
    if (features.get("spread_pct") or 0) > 0.5:
        risk += 0.25
    if (features.get("spread_pct") or 0) > 2:
        risk += 0.3
    if abs(features.get("chg_5", 0)) > 20:
        risk += 0.15
    if features.get("volume_ratio", 0) < 1:
        risk += 0.1
    risk = min(0.95, risk)
    if risk < 0.35:
        level = "LOW"
    elif risk < 0.6:
        level = "MEDIUM"
    else:
        level = "HIGH"
    return {"risk_probability": round(risk, 4), "level": level}


def run_quant_models(feature_payload: dict[str, Any]) -> dict[str, Any]:
    feats = feature_payload.get("features") or {}
    if not feature_payload.get("ready"):
        return {
            "pump_probability": 0.0,
            "direction_probability": {"LONG": 0.5, "SHORT": 0.5},
            "risk": {"risk_probability": 0.5, "level": "MEDIUM"},
            "model": "heuristic_v1",
        }
    pump = pump_probability(feats)
    direction = direction_probability(feats)
    risk = risk_probability(feats)
    return {
        "symbol": feature_payload.get("symbol"),
        "pump_probability": pump,
        "direction_probability": direction,
        "preferred_direction": "LONG" if direction["LONG"] >= direction["SHORT"] else "SHORT",
        "risk": risk,
        "model": "heuristic_v1",
        "note": "MVP heuristic. Replace with trained XGBoost when dataset ready.",
    }
