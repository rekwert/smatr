"""Unit tests for inefficiency-first feed policy."""

from __future__ import annotations

from app.services.inefficiency_feed import (
    FEED_ALL,
    FEED_INEFFICIENCY,
    FEED_VOLUME_SCAN,
    MIN_EDGE,
    MIN_EDGE_MAJOR,
    filter_and_sort,
    qualifies_inefficiency,
    should_persist_inefficiency,
    structure_confirmed,
)


def _row(**kwargs):
    base = {
        "symbol": "WIFUSDT",
        "feed": FEED_INEFFICIENCY,
        "setup_score": 70,
        "execution_score": 40,
        "edge_score": 75,
        "score": 70,
        "signal_type": "smc",
        "reason": {
            "feed": FEED_INEFFICIENCY,
            "checklist": {
                "liquidity_sweep": True,
                "fvg": True,
                "order_block": True,
            },
            "components": {
                "liquidity_sweep": 80,
                "fvg": 70,
                "order_block": 65,
            },
        },
    }
    base.update(kwargs)
    return base


def test_structure_requires_sweep_fvg_ob():
    assert structure_confirmed(
        checklist={"liquidity_sweep": True, "fvg": True, "order_block": True}
    )
    assert not structure_confirmed(
        checklist={"liquidity_sweep": True, "fvg": True, "order_block": False}
    )
    assert structure_confirmed(
        components={"liquidity_sweep": 60, "fvg": 55, "order_block": 50}
    )


def test_qualifies_rejects_volume_scan():
    r = _row(feed=FEED_VOLUME_SCAN, reason={"feed": FEED_VOLUME_SCAN, "checklist": {
        "liquidity_sweep": True, "fvg": True, "order_block": True
    }})
    assert not qualifies_inefficiency(r)


def test_major_needs_higher_edge():
    mid = _row(symbol="BTCUSDT", edge_score=MIN_EDGE + 5)  # 75 < 85
    assert not qualifies_inefficiency(mid)
    strong = _row(symbol="BTCUSDT", edge_score=MIN_EDGE_MAJOR)
    assert qualifies_inefficiency(strong)
    alt = _row(symbol="WIFUSDT", edge_score=MIN_EDGE)
    assert qualifies_inefficiency(alt)


def test_sort_edge_then_exec_then_setup():
    rows = [
        _row(symbol="A", edge_score=72, execution_score=50, setup_score=90, score=90),
        _row(symbol="B", edge_score=90, execution_score=30, setup_score=55, score=55),
        _row(symbol="C", edge_score=90, execution_score=60, setup_score=60, score=60),
    ]
    out = filter_and_sort(rows, feed=FEED_INEFFICIENCY, limit=10)
    assert [r["symbol"] for r in out] == ["C", "B", "A"]


def test_feed_all_includes_volume_scan():
    vol = _row(
        symbol="ETHUSDT",
        feed=FEED_VOLUME_SCAN,
        edge_score=40,
        reason={"feed": FEED_VOLUME_SCAN},
    )
    out = filter_and_sort([vol, _row()], feed=FEED_ALL, min_score=0, limit=10)
    assert len(out) == 2


def test_should_persist_gate():
    ok, _ = should_persist_inefficiency(
        {
            "symbol": "PEPEUSDT",
            "setup_score": 60,
            "execution_score": 35,
            "edge_score": 72,
            "reasons": {
                "checklist": {
                    "liquidity_sweep": True,
                    "fvg": True,
                    "order_block": True,
                }
            },
            "components": {},
        }
    )
    assert ok
    bad, why = should_persist_inefficiency(
        {
            "symbol": "BTCUSDT",
            "setup_score": 80,
            "execution_score": 50,
            "edge_score": 70,
            "reasons": {
                "checklist": {
                    "liquidity_sweep": True,
                    "fvg": True,
                    "order_block": True,
                }
            },
        }
    )
    assert not bad
    assert "edge" in why
