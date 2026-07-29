from app.backtesting.simulator import simulate_trade
from app.market_data.validation import validate_candle
from app.engines.regime.analyzer import MarketRegimeDetector
from app.engines.anomaly.detector import AnomalyDetector
from app.ai.guards import sanitize_text, validate_ai_payload
from app.ai.rating import compute_final_assessment
from app.market_data.orderbook import compute_orderbook_metrics
from tests.conftest import make_candles, trending_up


def test_validate_candle_rejects_bad_high():
    bad = make_candles([(100, 90, 99, 100, 10)])[0]  # high < open/close
    ok, reason = validate_candle(bad)
    assert not ok
    assert reason == "high_below_body"


def test_simulate_long_win():
    # entry 100, stop 95, target 110 — next bars hit target
    candles = make_candles(
        [
            (100, 101, 99, 100, 1000),
            (100, 112, 99.5, 111, 2000),
        ]
    )
    trade = simulate_trade(candles, entry=100, stop=95, target=110, direction="LONG", start_index=0)
    assert trade.result == "WIN"
    assert trade.rr > 0


def test_simulate_long_loss():
    candles = make_candles(
        [
            (100, 101, 99, 100, 1000),
            (100, 100.5, 94, 95, 2000),
        ]
    )
    trade = simulate_trade(candles, entry=100, stop=95, target=120, direction="LONG", start_index=0)
    assert trade.result == "LOSS"


def test_regime_and_anomaly():
    candles = trending_up(80)
    regime = MarketRegimeDetector().analyze(candles)
    assert "market_regime" in regime
    anomaly = AnomalyDetector().analyze(candles)
    assert "anomaly_score" in anomaly


def test_ai_guards_and_rating():
    text = sanitize_text("Это 100% сделка, покупай сейчас")
    assert "100%" not in text.lower() or "вероятностный" in text
    payload = validate_ai_payload(
        {"summary": "ok", "explanation": "гарантирован рост", "confidence": 150, "strengths": [], "risks": []}
    )
    assert payload["confidence"] == 100
    rating = compute_final_assessment(91, historical_probability=67, risk_level="medium", market_condition="trending")
    assert rating["confidence"] > 50
    assert "final_assessment" in rating


def test_orderbook_imbalance():
    metrics = compute_orderbook_metrics(
        {
            "bids": [[100, 5], [99, 4]],
            "asks": [[101, 1], [102, 1]],
        }
    )
    assert metrics["imbalance"] > 0
    assert metrics["pressure"] == "buy"
