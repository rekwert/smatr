from app.engines.fvg.analyzer import FVGAnalyzer
from tests.conftest import fvg_bullish_set


def test_bullish_fvg_detected():
    candles = fvg_bullish_set()
    events = FVGAnalyzer().detect_bullish_fvg(candles)
    assert events, "Expected bullish FVG"
    e = events[0]
    assert e.type == "bullish_fvg"
    assert e.top is not None and e.bottom is not None
    assert e.top > e.bottom
    assert e.strength > 0
