"""Unified market data models (Part 9 §7)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional


MarketType = Literal["future", "spot"]
Side = Literal["buy", "sell"]


@dataclass(slots=True)
class UnifiedCandle:
    exchange: str
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: int  # ms
    type: MarketType = "future"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_bar(self):
        from app.market_data.candles import CandleBar

        return CandleBar(
            timestamp=self.timestamp,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
        )


@dataclass(slots=True)
class UnifiedTrade:
    exchange: str
    symbol: str
    price: float
    quantity: float
    side: Side
    time: int  # ms
    value: Optional[float] = None

    def __post_init__(self) -> None:
        if self.value is None:
            self.value = self.price * self.quantity

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class UnifiedOrderbook:
    exchange: str
    symbol: str
    bids: list[list[float]]  # [price, size]
    asks: list[list[float]]
    timestamp: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class UnifiedTicker:
    exchange: str
    symbol: str
    last_price: float
    volume_24h: float
    change_pct_24h: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    open_interest: Optional[float] = None
    funding_rate: Optional[float] = None
    type: MarketType = "future"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class UnifiedSymbol:
    exchange: str
    symbol: str
    type: MarketType = "future"
    status: str = "active"
    volume_24h: float = 0.0
    price: Optional[float] = None
    base: Optional[str] = None
    quote: str = "USDT"
    listed_at: Optional[int] = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d
