from app.exchange_layer.base.models import UnifiedOrderbook
from app.exchange_layer.normalizer.symbols import normalize_symbol
from app.market_data.orderbook import compute_orderbook_metrics


def normalize_orderbook(
    exchange: str,
    symbol: str,
    bids: list[list[float]],
    asks: list[list[float]],
    timestamp_ms: int,
) -> dict:
    book = UnifiedOrderbook(
        exchange=exchange.lower(),
        symbol=normalize_symbol(symbol),
        bids=[[float(p), float(s)] for p, s in bids],
        asks=[[float(p), float(s)] for p, s in asks],
        timestamp=int(timestamp_ms),
    )
    metrics = compute_orderbook_metrics(book.to_dict())
    return {"book": book.to_dict(), "metrics": metrics}
