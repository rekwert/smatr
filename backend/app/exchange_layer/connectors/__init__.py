from app.exchange_layer.connectors.bybit import BybitExchange
from app.exchange_layer.connectors.okx import OkxExchange
from app.exchange_layer.connectors.bitget import BitgetExchange
from app.exchange_layer.connectors.mexc import MexcExchange
from app.exchange_layer.connectors.bingx import BingxExchange
from app.exchange_layer.connectors.kucoin import KucoinExchange
from app.exchange_layer.base.exchange_interface import ExchangeInterface

EXCHANGE_REGISTRY: dict[str, type[ExchangeInterface]] = {
    "bybit": BybitExchange,
    "okx": OkxExchange,
    "bitget": BitgetExchange,
    "mexc": MexcExchange,
    "bingx": BingxExchange,
    "kucoin": KucoinExchange,
}

# MVP priority order (Part 9 §18)
DEFAULT_EXCHANGES = ["bybit", "okx", "bitget", "mexc", "bingx", "kucoin"]


def create_exchange(name: str) -> ExchangeInterface:
    key = name.lower()
    if key not in EXCHANGE_REGISTRY:
        raise KeyError(f"Unknown exchange: {name}")
    return EXCHANGE_REGISTRY[key]()


def create_exchanges(names: list[str] | None = None) -> list[ExchangeInterface]:
    selected = names or DEFAULT_EXCHANGES
    return [create_exchange(n) for n in selected]


__all__ = [
    "BybitExchange",
    "OkxExchange",
    "BitgetExchange",
    "MexcExchange",
    "BingxExchange",
    "KucoinExchange",
    "EXCHANGE_REGISTRY",
    "DEFAULT_EXCHANGES",
    "create_exchange",
    "create_exchanges",
]
