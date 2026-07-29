from app.exchanges.base import ExchangeConnector
from app.exchanges.bybit import BybitClient
from app.exchanges.websocket import BybitWebSocket
from app.exchanges.binance import BinanceClient
from app.exchanges.okx import OkxClient


def get_primary_exchange() -> ExchangeConnector:
    return BybitClient()


__all__ = [
    "ExchangeConnector",
    "BybitClient",
    "BybitWebSocket",
    "BinanceClient",
    "OkxClient",
    "get_primary_exchange",
]
