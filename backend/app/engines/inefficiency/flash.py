"""Flash spike / wick-revert inefficiency detector.

Detects thin-market spikes that snap back toward a baseline (mean reversion).
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from app.market_data.candles import CandleBar


def detect_flash_inefficiency(
    candles: Sequence[CandleBar],
    *,
    lookback: int = 48,
    spike_pct: float = 6.0,
    snapback_ratio: float = 0.55,
    max_bars_open: int = 6,
) -> dict[str, Any]:
    """
    Returns detected=True when a recent bar (or short run) expands >= spike_pct
    vs local baseline and price has already reverted a meaningful fraction.
    """
    if len(candles) < max(20, lookback // 2):
        return {"detected": False}

    window = list(candles[-lookback:])
    closes = [float(c.close) for c in window]
    highs = [float(c.high) for c in window]
    lows = [float(c.low) for c in window]
    baseline = sorted(closes[:-3] or closes)[len(closes[:-3] or closes) // 2] if closes else 0.0
    if baseline <= 0:
        return {"detected": False}

    # ATR proxy of "normal" move
    ranges = [max(1e-12, h - l) for h, l in zip(highs[-20:], lows[-20:])]
    atr = sum(ranges) / max(1, len(ranges))
    atr_pct = atr / baseline * 100.0

    best: Optional[dict[str, Any]] = None
    for i in range(max(3, len(window) - 24), len(window)):
        c = window[i]
        # upward wick/spike
        up_pct = (float(c.high) - baseline) / baseline * 100.0
        # downward wick/spike
        dn_pct = (baseline - float(c.low)) / baseline * 100.0

        direction = None
        extreme = 0.0
        move_pct = 0.0
        if up_pct >= spike_pct and up_pct >= dn_pct:
            direction = "SHORT"  # fade the spike up
            extreme = float(c.high)
            move_pct = up_pct
        elif dn_pct >= spike_pct:
            direction = "LONG"  # fade the spike down
            extreme = float(c.low)
            move_pct = dn_pct
        else:
            continue

        # Must be abnormally large vs ATR
        if atr_pct > 0 and move_pct < max(spike_pct, atr_pct * 3.5):
            # still allow if absolute spike is very large
            if move_pct < spike_pct * 1.2:
                continue

        # Snapback: after spike bar, price returned toward baseline
        after = window[i + 1 : i + 1 + max_bars_open]
        if not after:
            # current bar still open — require wick already large vs close
            body_mid = (float(c.open) + float(c.close)) / 2.0
            if direction == "SHORT":
                reverted = (extreme - float(c.close)) / max(1e-12, extreme - baseline)
            else:
                reverted = (float(c.close) - extreme) / max(1e-12, baseline - extreme)
            if reverted < snapback_ratio * 0.7:
                continue
        else:
            last = after[-1]
            if direction == "SHORT":
                reverted = (extreme - float(last.close)) / max(1e-12, extreme - baseline)
            else:
                reverted = (float(last.close) - extreme) / max(1e-12, baseline - extreme)
            if reverted < snapback_ratio:
                continue

        cand = {
            "detected": True,
            "kind": "flash_spike",
            "direction": direction,
            "baseline": round(baseline, 8),
            "extreme": round(extreme, 8),
            "move_pct": round(move_pct, 2),
            "snapback_ratio": round(float(reverted), 3),
            "atr_pct": round(atr_pct, 3),
            "bar_index": i,
            "ceiling": round(extreme, 8) if direction == "SHORT" else None,
            "floor": round(extreme, 8) if direction == "LONG" else None,
            "hint": (
                f"Flash spike {move_pct:.1f}% → snapback к базе {baseline:.6g}. "
                f"Fade {direction}."
            ),
        }
        if best is None or cand["move_pct"] > best["move_pct"]:
            best = cand

    return best or {"detected": False}
