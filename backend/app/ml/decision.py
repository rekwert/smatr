"""Decision Engine — merge Quant ML + SMC + Liquidity (Part 13 §20)."""

from __future__ import annotations

from typing import Any, Optional


def decide(
    *,
    quant: dict[str, Any],
    smc_score: float = 0.0,
    hunter_score: float = 0.0,
    liquidity_score: float = 50.0,
) -> dict[str, Any]:
    pump_p = float(quant.get("pump_probability") or 0) * 100
    risk = quant.get("risk") or {}
    risk_level = risk.get("level", "MEDIUM")
    risk_pen = {"LOW": 0, "MEDIUM": 5, "HIGH": 15}.get(risk_level, 5)

    ai_score = (
        pump_p * 0.35
        + float(smc_score) * 0.30
        + float(hunter_score) * 0.20
        + float(liquidity_score) * 0.15
        - risk_pen
    )
    ai_score = int(max(0, min(100, round(ai_score))))

    if ai_score >= 85 and risk_level != "HIGH":
        action = "STRONG_WATCH"
    elif ai_score >= 70:
        action = "WATCH"
    elif ai_score >= 55:
        action = "CONTEXT"
    else:
        action = "IGNORE"

    return {
        "ai_score": ai_score,
        "action": action,
        "preferred_direction": quant.get("preferred_direction"),
        "pump_probability_pct": round(pump_p, 1),
        "risk_level": risk_level,
        "inputs": {
            "pump_probability_pct": round(pump_p, 1),
            "smc_score": smc_score,
            "hunter_score": hunter_score,
            "liquidity_score": liquidity_score,
        },
        "disclaimer": "Probabilistic assessment only. Not financial advice. Never 100%.",
    }
