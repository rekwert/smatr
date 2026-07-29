"""AI Rating Engine (Part 5 §11)."""

from __future__ import annotations

from typing import Any, Optional


def compute_final_assessment(
    algorithm_score: int,
    historical_probability: Optional[float] = None,
    risk_level: str = "medium",
    market_condition: str = "unknown",
) -> dict[str, Any]:
    hist = historical_probability if historical_probability is not None else 55.0
    risk_pen = {"low": 0, "medium": 3, "high": 8}.get(risk_level.lower(), 3)
    regime_boost = {
        "trending": 4,
        "accumulation": 3,
        "expansion": 2,
        "ranging": -2,
        "unknown": 0,
    }.get(market_condition.lower(), 0)

    confidence = int(
        round(
            algorithm_score * 0.55
            + hist * 0.35
            + 10
            + regime_boost
            - risk_pen
        )
    )
    confidence = max(0, min(100, confidence))

    if confidence >= 85 and algorithm_score >= 90:
        assessment = "Strong Setup"
    elif confidence >= 70:
        assessment = "Above Average Setup"
    elif confidence >= 55:
        assessment = "Average Setup"
    else:
        assessment = "Weak Setup"

    return {
        "final_assessment": assessment,
        "confidence": confidence,
        "inputs": {
            "algorithm_score": algorithm_score,
            "historical_probability": hist,
            "risk": risk_level,
            "market_condition": market_condition,
        },
    }
