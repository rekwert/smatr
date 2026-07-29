"""OKX adapter stub — not used in MVP (Bybit primary)."""

from __future__ import annotations

from typing import Any, Optional

from app.exchanges.base import ExchangeConnector
from app.market_data.candles import CandleBar


class OkxClient(ExchangeConnector):
    name = "okx"

    async def get_symbols(self) -> list[dict[str, Any]]:
        raise NotImplementedError("OKX adapter stub — enable in later sprint")

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "15",
        limit: int = 200,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> list[CandleBar]:
        raise NotImplementedError("OKX adapter stub")

    async def get_tickers(self) -> list[dict[str, Any]]:
        raise NotImplementedError("OKX adapter stub")

    async def get_orderbook(self, symbol: str, limit: int = 50) -> dict[str, Any]:
        raise NotImplementedError("OKX adapter stub")

    async def get_open_interest(self, symbol: str) -> Optional[dict[str, Any]]:
        raise NotImplementedError("OKX adapter stub")

    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        raise NotImplementedError("OKX adapter stub")
