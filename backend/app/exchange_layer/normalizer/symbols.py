"""Timeframe normalization helpers."""

from __future__ import annotations

# Canonical internal timeframes
CANONICAL_TF = {"1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"}

# Map various aliases → canonical
TF_ALIASES = {
    "1": "1m",
    "3": "3m",
    "5": "5m",
    "15": "15m",
    "30": "30m",
    "60": "1h",
    "240": "4h",
    "D": "1d",
    "1D": "1d",
    "1H": "1h",
    "4H": "4h",
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}


def to_canonical_tf(tf: str) -> str:
    key = tf.strip()
    if key in TF_ALIASES:
        return TF_ALIASES[key]
    low = key.lower()
    if low in TF_ALIASES:
        return TF_ALIASES[low]
    raise ValueError(f"Unsupported timeframe: {tf}")


def normalize_symbol(symbol: str) -> str:
    """Force SYMBOLUSDT uppercase without separators."""
    s = symbol.upper().replace("-", "").replace("_", "").replace("/", "")
    if s.endswith("USDTM"):
        s = s[:-1]
    return s
