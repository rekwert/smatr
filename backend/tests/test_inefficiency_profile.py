"""Tests: inefficiency profile + differentiated Edge (no more everyone=95)."""

from __future__ import annotations

from app.engines.inefficiency.profile import (
    compute_inefficiency_profile,
    filter_confirmed_items,
)
from app.engines.scoring.readiness import compute_edge_score


def _base_components(**over):
    c = {
        "liquidity_sweep": 70,
        "fvg": 65,
        "order_block": 60,
        "bos": 40,
        "volume": 25,
        "relative_volume": 0.9,
        "oi": 35,
        "orderflow": 30,
        "impulse_pct": 4.0,
        "impulse_bars": 2,
    }
    c.update(over)
    return c


def test_filter_noise_confirms():
    items = [
        "Volume mid-band 4.30M",
        "Spread 0.16%",
        "Very thin book",
        "Liquidity Sweep",
        "FVG / Imbalance",
    ]
    out = filter_confirmed_items(items)
    assert "Liquidity Sweep" in out
    assert all("mid-band" not in x for x in out)
    assert all("thin book" not in x.lower() for x in out)


def test_edge_not_capped_identical():
    weak = compute_edge_score(
        direction="LONG",
        components=_base_components(liquidity_sweep=55, fvg=52, order_block=51, impulse_pct=3, relative_volume=0.8, volume=20),
        checklist={"liquidity_sweep": True, "fvg": True, "order_block": True},
        pd={"zone": "discount"},
        risk_reward=2.8,
        liquidity_quality=25,
        volume_24h=2_000_000,
        setup_score=62,
        timing="Optimal",
    )
    strong = compute_edge_score(
        direction="LONG",
        components=_base_components(
            liquidity_sweep=92,
            fvg=88,
            order_block=85,
            impulse_pct=14,
            relative_volume=3.2,
            volume=78,
            oi=70,
            orderflow=65,
        ),
        checklist={"liquidity_sweep": True, "fvg": True, "order_block": True, "volume": True},
        pd={"zone": "discount"},
        risk_reward=3.1,
        liquidity_quality=20,
        volume_24h=800_000,
        setup_score=78,
        timing="Optimal",
    )
    assert weak["edge_score"] < strong["edge_score"]
    assert weak["edge_score"] < 90
    assert strong["edge_score"] >= weak["edge_score"] + 8
    # Weak RV must not reach elite band
    assert weak["edge_score"] <= 84


def test_profile_thesis_differs_by_rv_and_move():
    a = compute_inefficiency_profile(
        direction="LONG",
        components=_base_components(relative_volume=0.7, impulse_pct=3),
        checklist={"liquidity_sweep": True, "fvg": True, "order_block": True},
        pd={"zone": "discount"},
        volume_24h=4_000_000,
    )
    b = compute_inefficiency_profile(
        direction="LONG",
        components=_base_components(relative_volume=3.5, impulse_pct=12, volume=80),
        checklist={"liquidity_sweep": True, "fvg": True, "order_block": True},
        pd={"zone": "discount"},
        volume_24h=700_000,
    )
    assert a["inefficiency_strength"] != b["inefficiency_strength"]
    assert "RV×" in a["thesis"]
    assert a["entry_blockers"]  # weak volume → blockers
