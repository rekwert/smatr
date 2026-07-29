from app.exchange_layer.base.models import UnifiedTrade
from app.exchange_layer.normalizer.symbols import normalize_symbol


def normalize_trade(
    exchange: str,
    symbol: str,
    price: float,
    quantity: float,
    side: str,
    time_ms: int,
) -> UnifiedTrade:
    s = side.lower()
    if s in ("buy", "b", "bid", "long"):
        side_n = "buy"
    else:
        side_n = "sell"
    return UnifiedTrade(
        exchange=exchange.lower(),
        symbol=normalize_symbol(symbol),
        price=float(price),
        quantity=float(quantity),
        side=side_n,  # type: ignore[arg-type]
        time=int(time_ms),
    )
