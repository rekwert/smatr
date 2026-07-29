"""Order book metrics (Part 7 §9–10)."""

from __future__ import annotations

from typing import Any


def compute_orderbook_metrics(book: dict[str, Any], depth_levels: int = 10) -> dict[str, Any]:
    bids = book.get("bids") or []
    asks = book.get("asks") or []
    if not bids or not asks:
        return {
            "spread": None,
            "spread_pct": None,
            "bid_depth": 0.0,
            "ask_depth": 0.0,
            "imbalance": 0.0,
            "pressure": "unknown",
        }

    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])
    spread = best_ask - best_bid
    mid = (best_ask + best_bid) / 2 or 1e-12
    spread_pct = spread / mid * 100

    bid_depth = sum(float(p) * float(s) for p, s in bids[:depth_levels])
    ask_depth = sum(float(p) * float(s) for p, s in asks[:depth_levels])
    denom = bid_depth + ask_depth or 1e-12
    imbalance = (bid_depth - ask_depth) / denom

    if imbalance >= 0.25:
        pressure = "buy"
    elif imbalance <= -0.25:
        pressure = "sell"
    else:
        pressure = "balanced"

    return {
        "spread": round(spread, 10),
        "spread_pct": round(spread_pct, 4),
        "bid_depth": round(bid_depth, 2),
        "ask_depth": round(ask_depth, 2),
        "imbalance": round(imbalance * 100, 2),
        "pressure": pressure,
        "best_bid": best_bid,
        "best_ask": best_ask,
    }
