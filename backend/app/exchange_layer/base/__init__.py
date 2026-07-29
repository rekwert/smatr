"""Unified Exchange Interface (Part 9 §6)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from app.exchange_layer.base.models import (
    UnifiedCandle,
    UnifiedOrderbook,
    UnifiedSymbol,
    UnifiedTicker,
    UnifiedTrade,
)

CandleHandler = Callable[[UnifiedCandle], Awaitable[None] | None]
TradeHandler = Callable[[UnifiedTrade], Awaitable[None] | None]
OrderbookHandler = Callable[[UnifiedOrderbook], Awaitable[None] | None]


class ExchangeInterface(ABC):
    """All exchange adapters implement this — analyzers never talk to raw APIs."""

    name: str = "base"
    supports_futures: bool = True
    priority: int = 1  # higher = more preferred

    def __init__(self) -> None:
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    @abstractmethod
    async def get_symbols(self) -> list[UnifiedSymbol]:
        ...

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "15m",
        limit: int = 200,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> list[UnifiedCandle]:
        ...

    @abstractmethod
    async def get_tickers(self) -> list[UnifiedTicker]:
        ...

    @abstractmethod
    async def get_orderbook(self, symbol: str, limit: int = 50) -> UnifiedOrderbook:
        ...

    async def get_recent_trades(self, symbol: str, limit: int = 100) -> list[UnifiedTrade]:
        return []

    async def get_open_interest(self, symbol: str) -> Optional[dict[str, Any]]:
        return None

    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        return None

    async def subscribe_candles(
        self,
        symbols: list[str],
        timeframe: str,
        handler: CandleHandler,
    ) -> None:
        raise NotImplementedError(f"{self.name}: subscribe_candles not implemented")

    async def subscribe_trades(self, symbols: list[str], handler: TradeHandler) -> None:
        raise NotImplementedError(f"{self.name}: subscribe_trades not implemented")

    async def subscribe_orderbook(self, symbols: list[str], handler: OrderbookHandler) -> None:
        raise NotImplementedError(f"{self.name}: subscribe_orderbook not implemented")

    async def health_check(self) -> dict[str, Any]:
        import time

        t0 = time.perf_counter()
        try:
            await self.get_tickers()
            latency = (time.perf_counter() - t0) * 1000
            return {
                "exchange": self.name,
                "status": "online" if latency < 800 else "slow",
                "latency_ms": round(latency, 1),
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "exchange": self.name,
                "status": "down",
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                "error": str(exc),
            }
