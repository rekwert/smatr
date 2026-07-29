"""AI Context Builder (Part 5 §3)."""

from __future__ import annotations

from typing import Any, Optional


def build_ai_context(
    signal: dict[str, Any],
    *,
    similar: Optional[dict[str, Any]] = None,
    regime: Optional[dict[str, Any]] = None,
    orderbook: Optional[dict[str, Any]] = None,
    anomaly: Optional[dict[str, Any]] = None,
    trader_memory: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    reasons = signal.get("reason") or {}
    levels = {
        "entry": signal.get("entry"),
        "stop": signal.get("stop"),
        "target": signal.get("target"),
        "risk_reward": signal.get("risk_reward"),
        "risk_pct": signal.get("risk_pct"),
    }
    zones = signal.get("zones") or {}
    market = (signal.get("reason") or {}).get("market") or {}
    if not market and isinstance(signal.get("market"), dict):
        market = signal["market"]

    checklist = reasons.get("checklist") or {}
    found = reasons.get("found") or []

    return {
        "market": "crypto",
        "exchange": "bybit",
        "symbol": signal.get("symbol"),
        "timeframe": signal.get("timeframe"),
        "direction": signal.get("direction"),
        "signal_type": signal.get("signal_type"),
        "score": signal.get("score"),
        "structure": {
            "trend": (zones.get("premium_discount") or {}).get("zone"),
            "bos": bool(checklist.get("bos") or any("BOS" in str(x) for x in found)),
            "choch": any("CHoCH" in str(x) or "choch" in str(x).lower() for x in found),
            "ltf_trend": market.get("ltf_trend"),
            "htf_trend": market.get("htf_trend"),
        },
        "liquidity": {
            "sweep": next(
                (
                    e.get("direction")
                    for e in (zones.get("liquidity_sweeps") or [])
                    if isinstance(e, dict)
                ),
                None,
            ),
            "events": zones.get("liquidity_sweeps") or [],
            "equal_highs": zones.get("equal_highs") or [],
            "equal_lows": zones.get("equal_lows") or [],
        },
        "imbalance": {
            "fvg": zones.get("fvg") or [],
            "order_blocks": zones.get("order_blocks") or [],
        },
        "volume": {
            "relative_volume": market.get("rv"),
            "confirmed": bool(checklist.get("volume")),
        },
        "derivatives": {
            "oi_change_pct": market.get("oi_change_pct"),
            "funding": market.get("funding"),
        },
        "risk": levels,
        "events": found,
        "missing": reasons.get("missing") or [],
        "pump": reasons.get("pump"),
        "regime": regime,
        "orderbook": orderbook,
        "anomaly": anomaly,
        "similar": similar,
        "trader_memory": trader_memory,
        "disclaimer": (
            "Analytical context only. Not financial advice. "
            "No guaranteed outcomes."
        ),
    }
