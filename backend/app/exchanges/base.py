from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from app.market_data.candles import CandleBar


class ExchangeConnector(ABC):
    """Unified exchange interface (Part 7 §4). Primary production adapter: Bybit."""

    name: str = "base"

    @abstractmethod
    async def get_symbols(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "15",
        limit: int = 200,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> list[CandleBar]:
        ...

    @abstractmethod
    async def get_tickers(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def get_orderbook(self, symbol: str, limit: int = 50) -> dict[str, Any]:
        ...

    @abstractmethod
    async def get_open_interest(self, symbol: str) -> Optional[dict[str, Any]]:
        ...

    @abstractmethod
    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        ...
