"""Order-flow from recent trades (buy/sell notional imbalance)."""

from __future__ import annotations

from typing import Any, Sequence


def delta_from_trades(trades: Sequence[Any], *, direction: str = "LONG") -> dict[str, Any]:
    """
    trades: objects/dicts with side ('buy'|'sell') and size, price (or notional).
    Returns score 0..100 aligned with trade direction + raw imbalance.
    """
    buy = 0.0
    sell = 0.0
    for t in trades or []:
        if isinstance(t, dict):
            side = str(t.get("side") or "").lower()
            size = float(t.get("size") or t.get("qty") or 0)
            price = float(t.get("price") or 0)
        else:
            side = str(getattr(t, "side", "") or "").lower()
            size = float(getattr(t, "size", 0) or getattr(t, "qty", 0) or 0)
            price = float(getattr(t, "price", 0) or 0)
        notional = size * price if price > 0 else size
        if side in ("buy", "bid", "long"):
            buy += notional
        elif side in ("sell", "ask", "short"):
            sell += notional

    total = buy + sell
    if total <= 0:
        return {
            "score": 35.0,
            "buy_notional": 0.0,
            "sell_notional": 0.0,
            "imbalance": 0.0,
            "sample": 0,
        }

    imbalance = (buy - sell) / total  # -1..+1
    # Align to scenario direction
    aligned = imbalance if direction == "LONG" else -imbalance
    # Map: -0.4 → 15, 0 → 45, +0.15 → 62, +0.4 → 85
    score = 45.0 + aligned * 100.0
    score = max(5.0, min(95.0, score))

    return {
        "score": round(score, 1),
        "buy_notional": round(buy, 2),
        "sell_notional": round(sell, 2),
        "imbalance": round(imbalance, 4),
        "aligned": round(aligned, 4),
        "sample": len(trades),
    }
