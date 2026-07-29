"""Shared HTTP helper with rate limit + error mapping."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.exchange_layer.base.exceptions import (
    ApiTimeoutError,
    ExchangeLayerError,
    RateLimitError,
)
from app.exchange_layer.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)
_GLOBAL_LIMITER = RateLimiter(requests_per_second=10, burst=20)


async def http_get_json(
    url: str,
    *,
    params: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
    exchange: str = "unknown",
    timeout: float = 25.0,
) -> Any:
    await _GLOBAL_LIMITER.acquire(exchange)
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            resp = await client.get(url, params=params, headers=headers or {})
    except httpx.TimeoutException as exc:
        raise ApiTimeoutError(str(exc), exchange=exchange) from exc
    except httpx.HTTPError as exc:
        raise ExchangeLayerError(str(exc), exchange=exchange) from exc

    if resp.status_code == 429:
        raise RateLimitError("rate limited", exchange=exchange)
    if resp.status_code >= 400:
        raise ExchangeLayerError(f"HTTP {resp.status_code}: {resp.text[:200]}", exchange=exchange)
    try:
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        raise ExchangeLayerError(f"invalid json: {exc}", exchange=exchange) from exc
