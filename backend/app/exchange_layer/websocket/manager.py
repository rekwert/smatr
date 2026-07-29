"""Multi-exchange WebSocket manager (Part 9 §13).

MVP: REST-backed polling fan-in that presents the same queue interface as WS.
True native WS per exchange can replace pollers without changing consumers.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from app.exchange_layer.base.exchange_interface import ExchangeInterface
from app.exchange_layer.base.models import UnifiedCandle
from app.exchange_layer.connectors import create_exchanges
from app.exchange_layer.websocket.reconnect import ReconnectPolicy

logger = logging.getLogger(__name__)

CandleConsumer = Callable[[UnifiedCandle], Awaitable[None] | None]


class WebSocketManager:
    def __init__(self, exchanges: Optional[list[ExchangeInterface]] = None):
        self.exchanges = exchanges or create_exchanges(["bybit", "okx", "bitget"])
        self.queue: asyncio.Queue[UnifiedCandle] = asyncio.Queue(maxsize=10_000)
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()
        self._policy = ReconnectPolicy()

    async def start_candle_poll(
        self,
        symbols: list[str],
        timeframe: str = "15m",
        interval_sec: float = 15.0,
        consumer: Optional[CandleConsumer] = None,
    ) -> None:
        self._stop.clear()
        for ex in self.exchanges:
            self._tasks.append(
                asyncio.create_task(self._poll_exchange(ex, symbols, timeframe, interval_sec, consumer))
            )

    async def _poll_exchange(
        self,
        ex: ExchangeInterface,
        symbols: list[str],
        timeframe: str,
        interval_sec: float,
        consumer: Optional[CandleConsumer],
    ) -> None:
        await ex.connect()
        while not self._stop.is_set():
            try:
                for symbol in symbols:
                    candles = await ex.get_candles(symbol, timeframe=timeframe, limit=2)
                    if not candles:
                        continue
                    candle = candles[-1]
                    try:
                        self.queue.put_nowait(candle)
                    except asyncio.QueueFull:
                        _ = self.queue.get_nowait()
                        self.queue.put_nowait(candle)
                    if consumer:
                        result = consumer(candle)
                        if asyncio.iscoroutine(result):
                            await result
                self._policy.reset()
                await asyncio.sleep(interval_sec)
            except Exception as exc:  # noqa: BLE001
                logger.warning("%s candle poll error: %s", ex.name, exc)
                await self._policy.wait()

    async def stop(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()
        for ex in self.exchanges:
            await ex.disconnect()

    async def drain(self, max_items: int = 100) -> list[UnifiedCandle]:
        out: list[UnifiedCandle] = []
        while len(out) < max_items and not self.queue.empty():
            out.append(await self.queue.get())
        return out
