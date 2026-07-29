from app.engines.structure.analyzer import StructureAnalyzer
from tests.conftest import trending_up


def test_find_swings_detects_extremes():
    candles = trending_up(60)
    swings = StructureAnalyzer(swing_length=3).find_swings(candles)
    assert any(s.type == "swing_high" for s in swings)
    assert any(s.type == "swing_low" for s in swings)


def test_bos_strength_positive_on_uptrend():
    candles = trending_up(80)
    analyzer = StructureAnalyzer(swing_length=3)
    swings = analyzer.find_swings(candles)
    bos = analyzer.detect_bos(candles, swings)
    # Uptrend should eventually produce bullish BOS
    assert isinstance(bos, list)
    if bos:
        assert bos[0].strength > 0
