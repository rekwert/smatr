from app.engines.scoring.calculator import ScoreCalculator
from app.engines.pump_detector.analyzer import PumpDetector
from tests.conftest import trending_up, fvg_bullish_set


def test_score_calculator_returns_tier():
    candles = trending_up(100)
    result = ScoreCalculator().analyze_symbol("BTCUSDT", candles, timeframe="15")
    assert "score" in result
    assert result["tier"] in {"weak", "medium", "strong", "elite"}
    assert "reasons" in result
    assert "levels" in result
    assert "setup_score" in result
    assert "execution_score" in result
    assert "lifecycle_status" in result
    assert result["lifecycle_status"] in {
        "IGNORE",
        "WATCH",
        "SETUP_FORMING",
        "ENTRY_ZONE",
        "ENTRY_READY",
        "INVALIDATED",
    }
    assert "timing" in result


def test_sequence_fields_present():
    candles = fvg_bullish_set()
    result = ScoreCalculator().analyze_symbol("ENAUSDT", candles, timeframe="15", htf_trend="bullish")
    assert "sequence_valid" in result
    assert "checklist" in result["reasons"]
    assert isinstance(result["setup_score"], int)
    assert isinstance(result["execution_score"], int)
    assert 0 <= result["probability"] <= 100


def test_dual_score_short_discount_wait_retest():
    from app.engines.scoring.readiness import build_readiness_payload

    components = {
        "liquidity_sweep": 90,
        "bos": 85,
        "fvg": 80,
        "order_block": 88,
        "htf_trend": 90,
        "volume": 20,
        "oi": 15,
    }
    checklist = {k: components[k] >= 50 for k in components}
    payload = build_readiness_payload(
        direction="SHORT",
        components=components,
        checklist=checklist,
        sequence_valid=True,
        pd={"zone": "discount", "high": 0.19, "low": 0.16, "mid": 0.175},
        entry=0.17709,
        current_price=0.16857,
        tp1=0.1735,
        tp2=0.1703,
        stop=0.1793,
        risk_reward=3.0,
    )
    assert payload["setup_score"] >= 70
    assert payload["execution_score"] < 55
    assert payload["lifecycle_status"] in {"WATCH", "SETUP_FORMING"}
    assert payload["timing"] == "Late"
    assert payload["action"]["code"] == "WAIT_RETEST"
    assert payload["ideal_entry"] is not None
    assert payload["ideal_entry"] > payload["current_price"]
    assert payload["stop"] is not None
    assert float(payload["stop"]) > float(payload["ideal_entry"]), "SHORT stop must be above Ideal Entry"
    assert payload["tp1"] is not None and float(payload["tp1"]) < float(payload["ideal_entry"])
    inv_labels = " ".join(i["label"] for i in payload["invalidation"])
    assert str(round(float(payload["stop"]), 6)) in inv_labels or "выше" in inv_labels
    assert "0.164" not in inv_labels  # must not use wrong below-entry stop
    assert payload["why_no_entry"] and payload["why_no_entry"]["bullets"]
    assert any("Discount" in b or "Late" in b for b in payload["why_no_entry"]["bullets"])
    assert payload["execution_breakdown"]["parts"]
    assert payload["traffic_lights"]["timing"] == "🔴"
    assert "WAIT RETEST" in payload["action"]["title"] or payload["action"]["code"] == "WAIT_RETEST"
    assert payload["scenario_probability"] is not None
    assert payload["entry_probability_now"] is not None
    assert payload["entry_probability_now"] < payload["scenario_probability"]
    assert payload["invalidation"]
    assert payload["confidence_drivers"]
    assert payload["next_trigger"]
    assert payload["range_scale"] and payload["range_scale"]["price_pct"] is not None
    assert payload["liquidity_quality"] is not None
    assert payload["liquidity_stars"]
    assert payload["chasing_risk"] >= 70
    assert payload["chasing_level"] == "HIGH"
    assert payload["smart_money_activity"] in {"Accumulation", "Distribution", "Inactive"}
    assert payload["smart_money_stars"]
    assert payload["edge_score"] is not None
    assert payload["edge_reasons"]
    assert payload["replay"]


def test_setup_not_crushed_without_bos():
    from app.engines.scoring.readiness import build_readiness_payload

    components = {
        "liquidity_sweep": 85,
        "bos": 20,
        "fvg": 80,
        "order_block": 82,
        "htf_trend": 70,
        "volume": 55,
        "oi": 60,
        "orderflow": 58,
        "impulse_speed": 70,
        "post_impulse": 60,
    }
    checklist = {k: components[k] >= 50 for k in components}
    payload = build_readiness_payload(
        direction="LONG",
        components=components,
        checklist=checklist,
        sequence_valid=True,
        pd={"zone": "discount", "high": 110, "low": 90, "mid": 100},
        entry=98,
        current_price=98,
        stop=92,
        tp1=108,
        tp2=114,
        risk_reward=2.8,
        volume_24h=2_000_000,
    )
    assert payload["setup_score"] >= 65
    assert payload["timing"] == "Optimal"
    assert "рано" not in (payload["ai_conclusion"] or "").lower()
    assert "хорошей зоне" in (payload["ai_conclusion"] or "").lower()
    nt = payload["next_trigger"]
    assert nt and nt["title"] == "Следующее подтверждение"
    assert not any("вернётся" in c.lower() for c in nt["if_conditions"])
    assert payload["edge_score"] >= 55
    # Confirmed order: Sweep before BOS
    confirmed = payload["confirmed"]
    if "Liquidity Sweep" in confirmed and "BOS" in " ".join(confirmed):
        assert confirmed.index("Liquidity Sweep") < [
            i for i, c in enumerate(confirmed) if "BOS" in c
        ][0]


def test_sweep_thesis_beats_bos():
    """Sweep+FVG+OB without BOS should still produce a solid Setup."""
    from app.engines.scoring.readiness import compute_setup_score

    score = compute_setup_score(
        {
            "liquidity_sweep": 90,
            "fvg": 85,
            "order_block": 80,
            "oi": 70,
            "orderflow": 65,
            "volume": 60,
            "bos": 10,
        },
        direction="LONG",
        pd={"zone": "discount"},
        phase="Accumulation",
    )
    assert score >= 68


def test_pump_detector_score_bounds():
    candles = trending_up(80)
    pump = PumpDetector().analyze(candles, oi_change_pct=20)
    assert 0 <= pump["total"] <= 100
    assert "components" in pump
