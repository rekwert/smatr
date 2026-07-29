"""Feature Engineering for Quant AI (Part 13 §4–11)."""

from __future__ import annotations

from typing import Any, Optional, Sequence

from app.engines.liquidity.analyzer import LiquidityAnalyzer
from app.engines.structure.analyzer import StructureAnalyzer
from app.engines.volume.analyzer import VolumeAnalyzer
from app.market_data.candles import CandleBar, atr


def extract_features(
    symbol: str,
    candles: Sequence[CandleBar],
    *,
    oi_change: float = 0.0,
    funding: Optional[float] = None,
    orderbook_imbalance: Optional[float] = None,
    spread_pct: Optional[float] = None,
    bid_depth: float = 0.0,
    ask_depth: float = 0.0,
    btc_trend: str = "unknown",
) -> dict[str, Any]:
    if len(candles) < 30:
        return {"symbol": symbol, "features": {}, "ready": False}

    last = candles[-1]
    c1 = candles[-2]
    c5 = candles[-6] if len(candles) > 6 else candles[0]
    c60 = candles[-60] if len(candles) >= 60 else candles[0]

    def chg(a: CandleBar, b: CandleBar) -> float:
        return (b.close - a.close) / (a.close or 1e-9) * 100

    vol = VolumeAnalyzer().analyze(candles)
    structure = StructureAnalyzer()
    swings = structure.find_swings(candles)
    trend = structure.current_trend(swings)
    bos = structure.detect_bos(candles, swings)
    sweeps = LiquidityAnalyzer().detect_sweep(candles, swings)

    cur_atr = atr(candles, 14)
    avg_atr = atr(candles[:-14] if len(candles) > 40 else candles, 14) or 1e-9
    atr_compression = 1 - min(1.0, cur_atr / avg_atr)

    # EMA-ish via simple SMA proxies
    def sma(n: int) -> float:
        w = candles[-n:]
        return sum(x.close for x in w) / len(w)

    sma20 = sma(min(20, len(candles)))
    sma50 = sma(min(50, len(candles)))

    features = {
        # price
        "chg_1": chg(c1, last),
        "chg_5": chg(c5, last),
        "chg_60": chg(c60, last),
        "atr": cur_atr,
        "atr_compression": round(max(0.0, atr_compression), 4),
        "range_pct": last.range / (last.close or 1e-9) * 100,
        "dist_sma20_pct": (last.close - sma20) / (sma20 or 1e-9) * 100,
        "dist_sma50_pct": (last.close - sma50) / (sma50 or 1e-9) * 100,
        # volume
        "volume_ratio": vol["rv"],
        "volume_spike": 1 if vol["spike"] else 0,
        # structure / smc
        "liquidity_sweep": 1 if sweeps else 0,
        "sweep_direction": sweeps[0].direction if sweeps else None,
        "bos": 1 if bos else 0,
        "bos_direction": bos[0].direction if bos else None,
        "structure_trend": trend,
        # book / deriv
        "orderbook_imbalance": orderbook_imbalance or 0.0,
        "spread_pct": spread_pct or 0.0,
        "bid_depth": bid_depth,
        "ask_depth": ask_depth,
        "oi_change": oi_change,
        "funding": funding or 0.0,
        # context
        "btc_trend_bullish": 1 if btc_trend == "bullish" else 0,
        "btc_trend_bearish": 1 if btc_trend == "bearish" else 0,
    }
    return {"symbol": symbol.upper(), "features": features, "ready": True}
