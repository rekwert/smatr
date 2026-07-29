from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.config.constants import BYBIT_INTERVAL_MAP
from app.config.settings import settings
from app.exchanges.base import ExchangeConnector
from app.market_data.candles import CandleBar

logger = logging.getLogger(__name__)


class BybitClient(ExchangeConnector):
    """Bybit V5 public market data client (linear USDT perpetual)."""

    name = "bybit"

    def __init__(
        self,
        base_url: Optional[str] = None,
        category: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = (base_url or settings.bybit_base_url).rstrip("/")
        self.category = category or settings.bybit_category
        self.timeout = timeout

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        # trust_env=False — игнор системного HTTP_PROXY (иначе ConnectTimeout к Bybit)
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        if data.get("retCode") != 0:
            raise RuntimeError(f"Bybit error {data.get('retCode')}: {data.get('retMsg')}")
        return data.get("result") or {}

    @staticmethod
    def normalize_interval(timeframe: str) -> str:
        key = timeframe.strip()
        if key not in BYBIT_INTERVAL_MAP:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return BYBIT_INTERVAL_MAP[key]

    async def get_instruments(self, limit: int = 1000) -> list[dict[str, Any]]:
        result = await self._get(
            "/v5/market/instruments-info",
            {"category": self.category, "limit": min(limit, 1000)},
        )
        items = result.get("list") or []
        # Only trading USDT linear perpetuals
        out = []
        for item in items:
            if item.get("status") != "Trading":
                continue
            if item.get("quoteCoin") != "USDT":
                continue
            if item.get("contractType") not in (None, "LinearPerpetual", "LinearFutures"):
                # Keep LinearPerpetual primarily
                if item.get("contractType") and "Linear" not in str(item.get("contractType")):
                    continue
            out.append(item)
        return out

    async def get_symbols(self) -> list[dict[str, Any]]:
        return await self.get_instruments()

    async def get_tickers(self) -> list[dict[str, Any]]:
        result = await self._get("/v5/market/tickers", {"category": self.category})
        return result.get("list") or []

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = "15",
        limit: int = 200,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> list[CandleBar]:
        return await self.get_klines(symbol, timeframe=timeframe, limit=limit, start=start, end=end)

    async def get_orderbook(self, symbol: str, limit: int = 50) -> dict[str, Any]:
        result = await self._get(
            "/v5/market/orderbook",
            {"category": self.category, "symbol": symbol.upper(), "limit": min(limit, 200)},
        )
        bids = [[float(p), float(s)] for p, s in (result.get("b") or [])]
        asks = [[float(p), float(s)] for p, s in (result.get("a") or [])]
        return {"symbol": symbol.upper(), "bids": bids, "asks": asks, "ts": result.get("ts")}

    async def get_klines(
        self,
        symbol: str,
        timeframe: str = "15",
        limit: int = 200,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> list[CandleBar]:
        interval = self.normalize_interval(timeframe)
        params: dict[str, Any] = {
            "category": self.category,
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": min(limit, 1000),
        }
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end

        result = await self._get("/v5/market/kline", params)
        rows = result.get("list") or []
        # Bybit returns newest first
        bars: list[CandleBar] = []
        for row in reversed(rows):
            bars.append(
                CandleBar(
                    timestamp=int(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
            )
        return bars

    async def get_funding_rate(self, symbol: str) -> Optional[float]:
        result = await self._get(
            "/v5/market/tickers",
            {"category": self.category, "symbol": symbol.upper()},
        )
        items = result.get("list") or []
        if not items:
            return None
        raw = items[0].get("fundingRate")
        return float(raw) if raw is not None else None

    async def get_open_interest(self, symbol: str, interval: str = "1h") -> Optional[dict[str, Any]]:
        result = await self._get(
            "/v5/market/open-interest",
            {
                "category": self.category,
                "symbol": symbol.upper(),
                "intervalTime": interval,
                "limit": 2,
            },
        )
        items = result.get("list") or []
        if not items:
            return None
        # newest first typically
        latest = items[0]
        prev = items[1] if len(items) > 1 else None
        oi = float(latest.get("openInterest", 0))
        prev_oi = float(prev.get("openInterest", oi)) if prev else oi
        change_pct = ((oi - prev_oi) / prev_oi * 100.0) if prev_oi else 0.0
        return {"oi": oi, "oi_change_pct": change_pct}
