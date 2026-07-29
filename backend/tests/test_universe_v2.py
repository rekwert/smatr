"""Universe Engine v2 unit tests (no live exchanges)."""

from __future__ import annotations

from app.universe.cheap_filter import apply_cheap_filter, assign_tier, cheap_score
from app.universe.cross_exchange import find_cross_inefficiencies
from app.universe.models import UniverseRow


def test_assign_tiers():
    assert assign_tier(2_000_000, None) == "A"
    assert assign_tier(200_000, None) == "B"
    assert assign_tier(2_000_000, 5.0) == "C"
    assert assign_tier(50_000, None) == "SKIP"


def test_cheap_filter_excludes_majors_and_keeps_mid():
    rows = [
        UniverseRow(exchange="bybit", symbol="BTCUSDT", price=100, volume_24h=1_000_000_000, change_pct_24h=1),
        UniverseRow(
            exchange="mexc",
            symbol="XYZUSDT",
            price=0.01,
            volume_24h=2_000_000,
            change_pct_24h=9,
            spread_pct=0.3,
            liquidity_score=42,
        ),
        UniverseRow(
            exchange="okx",
            symbol="ABCUSDT",
            price=1.0,
            volume_24h=250_000,
            change_pct_24h=4,
            spread_pct=0.4,
            liquidity_score=35,
        ),
    ]
    out = apply_cheap_filter(rows, max_candidates=50, min_cheap_score=10)
    symbols = {r.symbol for r in out}
    assert "BTCUSDT" not in symbols
    assert "XYZUSDT" in symbols


def test_cross_exchange_gap():
    rows = [
        UniverseRow(exchange="bybit", symbol="XYZUSDT", price=0.0050, volume_24h=1_000_000),
        UniverseRow(exchange="mexc", symbol="XYZUSDT", price=0.0058, volume_24h=2_000_000),
    ]
    opps = find_cross_inefficiencies(rows, min_spread_pct=1.0)
    assert len(opps) == 1
    assert opps[0].spread_pct >= 15


def test_cheap_score_reasons():
    row = UniverseRow(
        exchange="bitget",
        symbol="LOWUSDT",
        price=1,
        volume_24h=3_000_000,
        change_pct_24h=10,
        spread_pct=0.25,
        liquidity_score=40,
        tier="A",
    )
    s = cheap_score(row)
    assert s >= 40
    assert row.reasons
