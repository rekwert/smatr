"""Volume intelligence with session-aware RV (Part 7 §12–13)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from app.market_data.candles import CandleBar


SESSION_HOURS = {
    "asia": range(0, 8),
    "london": range(8, 13),
    "ny": range(13, 21),
    "off": range(21, 24),
}


def session_name(ts_ms: int) -> str:
    hour = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).hour
    for name, hours in SESSION_HOURS.items():
        if hour in hours:
            return name
    return "off"


def relative_volume_smart(candles: Sequence[CandleBar], lookback: int = 40) -> dict:
    if not candles:
        return {"rv": 0.0, "session": "unknown", "rating": "weak", "anomaly": False}

    last = candles[-1]
    sess = session_name(last.timestamp)
    peers = [
        c
        for c in candles[-(lookback + 1) : -1]
        if session_name(c.timestamp) == sess
    ]
    if len(peers) < 3:
        peers = list(candles[-(lookback + 1) : -1])
    avg = sum(c.volume for c in peers) / len(peers) if peers else 0.0
    rv = (last.volume / avg) if avg > 0 else 0.0

    if rv >= 8:
        rating, anomaly = "extreme", True
    elif rv >= 5:
        rating, anomaly = "anomaly", True
    elif rv >= 2:
        rating, anomaly = "elevated", False
    elif rv >= 1:
        rating, anomaly = "normal", False
    else:
        rating, anomaly = "weak", False

    return {
        "rv": round(rv, 2),
        "session": sess,
        "rating": rating,
        "anomaly": anomaly,
        "peer_count": len(peers),
    }
