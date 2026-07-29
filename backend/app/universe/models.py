"""Market Universe Engine v2 — 3-level scan architecture.

Level 1: ALL USDT perps from 6 exchanges → normalize
Level 2: Cheap filter (volume tiers, spread, liquidity, majors exclude, new listings)
Level 3: Heavy SMC + derivatives + AI ranking on shortlist
Bonus: Cross-exchange inefficiency scanner
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional

Tier = Literal["A", "B", "C", "SKIP"]


# Majors we skip in hunter tiers (not our edge)
DEFAULT_EXCLUDE = {
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "DOTUSDT",
    "LINKUSDT",
    "LTCUSDT",
    "BCHUSDT",
    "TRXUSDT",
    "TONUSDT",
    "SUIUSDT",
}


@dataclass
class UniverseRow:
    exchange: str
    symbol: str  # normalized BTCUSDT
    raw_symbol: str = ""
    price: float = 0.0
    volume_24h: float = 0.0
    change_pct_24h: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    spread_pct: Optional[float] = None
    open_interest: Optional[float] = None
    funding_rate: Optional[float] = None
    listed_at: Optional[int] = None  # ms
    age_days: Optional[float] = None
    liquidity_score: float = 0.0
    volume_ratio_proxy: float = 1.0
    vol_expansion_proxy: float = 0.0
    cheap_score: float = 0.0
    tier: Tier = "SKIP"
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CrossOpportunity:
    symbol: str
    low_exchange: str
    high_exchange: str
    low_price: float
    high_price: float
    spread_pct: float
    volume_low: float
    volume_high: float
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HeavyCandidate:
    exchange: str
    symbol: str
    score: int
    direction: str
    tier: str
    cheap_score: float
    smc_score: float
    ai_score: float
    pump_probability_pct: float
    risk_level: str
    reasons: list[str]
    liquidity_score: float
    volume_24h: float
    oi_change_pct: Optional[float] = None
    funding: Optional[float] = None
    entry: Optional[float] = None
    stop: Optional[float] = None
    target: Optional[float] = None
    # Full SMC readiness snapshot for Signal Card
    analysis: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
