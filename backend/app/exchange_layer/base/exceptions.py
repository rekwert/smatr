"""Exchange layer exceptions (Part 9 §15)."""

from __future__ import annotations


class ExchangeLayerError(Exception):
    code: str = "exchange_error"

    def __init__(self, message: str, exchange: str | None = None):
        self.exchange = exchange
        super().__init__(message)


class ConnectionLostError(ExchangeLayerError):
    code = "connection_lost"


class ApiTimeoutError(ExchangeLayerError):
    code = "api_timeout"


class InvalidSymbolError(ExchangeLayerError):
    code = "invalid_symbol"


class RateLimitError(ExchangeLayerError):
    code = "rate_limit"


class ExchangeMaintenanceError(ExchangeLayerError):
    code = "maintenance"
