"""Domain constants and default score weights (Part 2 §11)."""

from __future__ import annotations

BYBIT_INTERVAL_MAP = {
    "1m": "1",
    "3m": "3",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "4h": "240",
    "1d": "D",
    "1": "1",
    "3": "3",
    "5": "5",
    "15": "15",
    "30": "30",
    "60": "60",
    "240": "240",
    "D": "D",
}

SWING_LENGTH_DEFAULT = 3
EQUAL_LEVEL_THRESHOLD_PCT = 0.15
LIQUIDITY_SWEEP_MIN_PIERCE_PCT = 0.05
VOLUME_SPIKE_MULTIPLIER = 5.0
ATR_COMPRESSION_RATIO = 0.45

# Primary thesis weights (sum ≈ 100) — Sweep/FVG/OB first; BOS is confirmation
DEFAULT_SMC_WEIGHTS = {
    "liquidity_sweep": 20,
    "fvg": 18,
    "order_block": 15,
    "oi": 15,
    "orderflow": 15,
    "volume": 8,
    "zone_align": 5,
    "bos": 3,
    "htf_trend": 1,
}

# Pump score weights (Part 2 §10.5)
DEFAULT_PUMP_WEIGHTS = {
    "compression": 20,
    "volume_increase": 20,
    "breakout": 20,
    "oi_increase": 15,
    "liquidity": 10,
    "market_cap": 10,
    "momentum": 5,
}

SCORE_TIER_WEAK = 50
SCORE_TIER_MEDIUM = 75
SCORE_TIER_STRONG = 90

DISCLAIMER = (
    "Analytical tool only. Not financial advice. "
    "Past patterns do not guarantee future results. "
    "No automated trade execution."
)
