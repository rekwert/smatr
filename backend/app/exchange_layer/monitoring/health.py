"""Exchange health / latency monitoring (Part 9 §16)."""

from __future__ import annotations

import asyncio
from typing import Optional

from app.exchange_layer.base.exchange_interface import ExchangeInterface
from app.exchange_layer.connectors import create_exchanges


async def check_all_exchanges(
    exchanges: Optional[list[ExchangeInterface]] = None,
) -> list[dict]:
    adapters = exchanges or create_exchanges()
    results = await asyncio.gather(*[ex.health_check() for ex in adapters], return_exceptions=True)
    out: list[dict] = []
    for ex, res in zip(adapters, results):
        if isinstance(res, Exception):
            out.append(
                {
                    "exchange": ex.name,
                    "status": "down",
                    "latency_ms": None,
                    "error": str(res),
                }
            )
        else:
            out.append(res)
    return out


def status_emoji(status: str) -> str:
    return {"online": "🟢", "slow": "🟡", "degraded": "🟡", "down": "🔴"}.get(status, "⚪")
