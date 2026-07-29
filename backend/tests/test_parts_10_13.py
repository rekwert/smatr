from app.engines.hunter.analyzer import LowLiquidityHunter, hunter_status
from app.strategy.engine import StrategyEngine
from app.ml.features import extract_features
from app.ml.models import run_quant_models, pump_probability
from app.ml.decision import decide
from tests.conftest import trending_up, make_candles


def test_hunter_status_tiers():
    assert hunter_status(96) == "ACTIVE"
    assert hunter_status(90) == "READY"
    assert hunter_status(75) == "PREPARING"
    assert hunter_status(55) == "SLEEPING"


def test_hunter_detects_compression_bias():
    # flat-ish range with rising volume
    pattern = []
    for i in range(80):
        vol = 1000 + i * 40
        pattern.append((100, 100.4, 99.7, 100.1, vol))
    candles = make_candles(pattern)
    res = LowLiquidityHunter().analyze("XYZUSDT", candles, exchange="mexc", volume_24h=12_000_000)
    assert res["score"] >= 0
    assert "status" in res
    assert "components" in res


def test_strategy_plan_has_rr_and_size():
    candles = trending_up(100)
    plan = StrategyEngine().build_plan("BTCUSDT", candles, account_balance=10_000, risk_profile="normal")
    assert plan["entry"]
    assert plan["stop_loss"]
    assert plan["targets"]["tp1"]
    assert plan["risk_reward"] is not None
    assert plan["position"]["notional"] > 0
    assert plan["confidence"] >= 0


def test_ml_features_and_decision():
    candles = trending_up(100)
    feats = extract_features("BTCUSDT", candles, oi_change=20, btc_trend="bullish")
    assert feats["ready"]
    quant = run_quant_models(feats)
    assert 0 <= quant["pump_probability"] <= 1
    d = decide(quant=quant, smc_score=80, hunter_score=70, liquidity_score=60)
    assert 0 <= d["ai_score"] <= 100
    assert d["action"] in {"STRONG_WATCH", "WATCH", "CONTEXT", "IGNORE"}


def test_pump_probability_penalizes_extension():
    low = pump_probability({"atr_compression": 0.1, "volume_ratio": 1, "chg_5": 40})
    high = pump_probability({"atr_compression": 0.8, "volume_ratio": 8, "volume_spike": 1, "liquidity_sweep": 1, "bos": 1, "oi_change": 30})
    assert high > low
