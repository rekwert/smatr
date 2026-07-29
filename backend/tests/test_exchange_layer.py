from app.exchange_layer.normalizer.symbols import normalize_symbol, to_canonical_tf
from app.exchange_layer.scanners import liquidity_score
from app.exchange_layer.base.models import UnifiedCandle
from app.exchange_layer.connectors import EXCHANGE_REGISTRY, create_exchange
from app.exchange_layer.websocket.reconnect import ReconnectPolicy


def test_normalize_symbol():
    assert normalize_symbol("btc-usdt") == "BTCUSDT"
    assert normalize_symbol("ETH_USDT") == "ETHUSDT"


def test_canonical_tf():
    assert to_canonical_tf("15") == "15m"
    assert to_canonical_tf("60") == "1h"
    assert to_canonical_tf("D") == "1d"


def test_liquidity_score_bounds():
    assert 0 <= liquidity_score(0) <= 100
    assert liquidity_score(100_000_000, depth_usd=5_000_000, spread_pct=0.01) > 70


def test_unified_candle_to_bar():
    c = UnifiedCandle(
        exchange="bybit",
        symbol="BTCUSDT",
        timeframe="15m",
        open=1,
        high=2,
        low=0.5,
        close=1.5,
        volume=10,
        timestamp=1_700_000_000_000,
    )
    bar = c.to_bar()
    assert bar.close == 1.5
    assert bar.timestamp == 1_700_000_000_000


def test_registry_has_all_exchanges():
    expected = {"bybit", "okx", "bitget", "mexc", "bingx", "kucoin"}
    assert expected.issubset(set(EXCHANGE_REGISTRY.keys()))
    for name in expected:
        ex = create_exchange(name)
        assert ex.name == name
        assert ex.priority > 0


def test_reconnect_policy_increments():
    p = ReconnectPolicy(base_delay=0.01, max_delay=0.05)
    assert p._attempt == 0
