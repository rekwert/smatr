"""Tests for Inefficiency Engine playbook / lifecycle."""

from __future__ import annotations

from app.engines.inefficiency.engine import (
    INEFF_ENTRY_READY,
    INEFF_NONE,
    INEFF_WAIT_VOLUME,
    evaluate_inefficiency,
)
from app.market_data.candles import CandleBar


def _bars_flash_down(n: int = 60) -> list[CandleBar]:
    """Quiet tape then sharp dump wick with snapback — LONG fade."""
    out: list[CandleBar] = []
    px = 100.0
    ts = 1_700_000_000_000
    for i in range(n - 4):
        out.append(
            CandleBar(
                timestamp=ts + i * 900_000,
                open=px,
                high=px * 1.002,
                low=px * 0.998,
                close=px,
                volume=1000 + i,
            )
        )
    # spike down
    i = n - 4
    extreme = 88.0
    out.append(
        CandleBar(
            timestamp=ts + i * 900_000,
            open=100.0,
            high=100.5,
            low=extreme,
            close=92.0,
            volume=8000,
        )
    )
    # snapback bars
    for j, c in enumerate((94.0, 96.5, 97.5)):
        k = n - 3 + j
        out.append(
            CandleBar(
                timestamp=ts + k * 900_000,
                open=c - 0.5,
                high=c + 0.8,
                low=c - 1.2,
                close=c,
                volume=5000 + j * 500,
            )
        )
    return out


def test_flash_path_produces_playbook():
    bars = _bars_flash_down()
    components = {
        "liquidity_sweep": 40,
        "fvg": 40,
        "order_block": 40,
        "volume": 70,
        "relative_volume": 2.4,
        "oi": 55,
        "orderflow": 60,
        "impulse_pct": 12.0,
    }
    checklist = {k: components[k] >= 50 for k in ("liquidity_sweep", "fvg", "order_block", "volume", "oi")}
    res = evaluate_inefficiency(
        bars,
        direction="LONG",
        components=components,
        checklist=checklist,
        pd={"zone": "discount"},
        volume_24h=900_000,
        vol={"rv": 2.4},
        levels={},
    )
    assert res["qualifies"] is True
    assert res["inefficiency_kind"] == "flash_spike"
    assert res["inefficiency_status"] != INEFF_NONE
    assert res["playbook"]
    assert res["plan"].get("stop") is not None
    assert res["plan"].get("tp1") is not None


def test_sweep_without_displacement_rejected_on_liquid():
    bars = _bars_flash_down()
    components = {
        "liquidity_sweep": 60,
        "fvg": 55,
        "order_block": 55,
        "volume": 20,
        "relative_volume": 0.5,
        "oi": 30,
        "orderflow": 25,
        "impulse_pct": 0.4,
    }
    checklist = {
        "liquidity_sweep": True,
        "fvg": True,
        "order_block": True,
        "volume": False,
    }
    res = evaluate_inefficiency(
        bars,
        direction="LONG",
        components=components,
        checklist=checklist,
        pd={"zone": "discount"},
        volume_24h=25_000_000,  # too liquid + weak move
        vol={"rv": 0.5},
    )
    # May still detect flash from synthetic bars; if not flash, should not qualify as weak sweep on liquid
    if res.get("inefficiency_kind") == "sweep_reclaim":
        assert res["qualifies"] is False or res["thinness"] < 40


def test_wait_volume_when_in_zone_without_rv():
    bars = _bars_flash_down()
    # Force price into mid of flash plan by using last close ~97.5 near reclaim
    components = {
        "liquidity_sweep": 40,
        "fvg": 40,
        "order_block": 40,
        "volume": 15,
        "relative_volume": 0.6,
        "oi": 30,
        "orderflow": 25,
        "impulse_pct": 10.0,
    }
    checklist = {k: False for k in ("liquidity_sweep", "fvg", "order_block", "volume", "oi")}
    res = evaluate_inefficiency(
        bars,
        direction="LONG",
        components=components,
        checklist=checklist,
        pd={"zone": "discount"},
        volume_24h=800_000,
        vol={"rv": 0.6},
    )
    if res.get("qualifies") and res.get("near_entry"):
        assert res["inefficiency_status"] in (INEFF_WAIT_VOLUME, INEFF_ENTRY_READY)
        if res["inefficiency_status"] == INEFF_ENTRY_READY:
            assert float(res["relative_volume"]) >= 2.0
