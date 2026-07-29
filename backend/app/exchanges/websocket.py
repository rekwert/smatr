"""Bybit public WebSocket manager (linear).

Consumes kline confirms and pushes into an in-memory / Redis-friendly handler.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Optional

import websockets

from app.config.settings import settings

logger = logging.getLogger(__name__)

MessageHandler = Callable[[dict[str, Any]], Awaitable[None] | None]


class BybitWebSocket:
    def __init__(
        self,
        url: Optional[str] = None,
        on_message: Optional[MessageHandler] = None,
    ):
        self.url = url or settings.bybit_ws_url
        self.on_message = on_message
        self._stop = asyncio.Event()

    def subscribe_payload(self, topics: list[str]) -> str:
        return json.dumps({"op": "subscribe", "args": topics})

    @staticmethod
    def kline_topic(interval: str, symbol: str) -> str:
        return f"kline.{interval}.{symbol.upper()}"

    async def run(self, topics: list[str]) -> None:
        while not self._stop.is_set():
            try:
                async with websockets.connect(self.url, ping_interval=20) as ws:
                    # Bybit recommends ping every ~20s; library handles keepalive.
                    await ws.send(self.subscribe_payload(topics))
                    logger.info("Bybit WS subscribed to %d topics", len(topics))
                    async for raw in ws:
                        if self._stop.is_set():
                            break
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if self.on_message:
                            result = self.on_message(msg)
                            if asyncio.iscoroutine(result):
                                await result
            except Exception as exc:  # noqa: BLE001
                logger.warning("Bybit WS disconnected: %s; retry in 3s", exc)
                await asyncio.sleep(3)

    def stop(self) -> None:
        self._stop.set()
