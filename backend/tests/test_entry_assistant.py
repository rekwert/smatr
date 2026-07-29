"""Entry Assistant status logic tests."""

from __future__ import annotations

from app.strategy.entry_assistant import MODE_TRIGGERS, STATUS_RU, EntryAssistant


def test_modes_defined():
    assert "liquidity_sweep" in MODE_TRIGGERS["conservative"]
    assert "bos" in MODE_TRIGGERS["balanced"]
    assert "ai_high" in MODE_TRIGGERS["aggressive"]


def test_status_labels_ru():
    assert STATUS_RU["ENTRY_READY"] == "ГОТОВ К ВХОДУ"
    assert STATUS_RU["MISSED"] == "ОПОЗДАЛИ"


def test_mode_satisfied():
    ea = EntryAssistant()
    triggers = {
        "liquidity_sweep": {"ok": True},
        "bos": {"ok": True},
        "fvg": {"ok": True},
        "oi": {"ok": True},
        "choch": {"ok": False},
        "volume": {"ok": False},
        "compression_or_anomaly": {"ok": False},
        "ai_high": {"ok": False},
    }
    assert ea._mode_satisfied(triggers, "balanced") is True
    assert ea._mode_satisfied(triggers, "conservative") is False


def test_resolve_entry_ready():
    ea = EntryAssistant()
    status = ea._resolve_status(
        invalidated=False,
        missed=False,
        in_zone=True,
        mode_ok=True,
        triggers={"liquidity_sweep": {"ok": True}},
        distance_pct=0,
        direction="LONG",
        score=90,
        phase="accumulation",
    )
    assert status == "ENTRY_READY"


def test_resolve_missed_and_invalid():
    ea = EntryAssistant()
    assert (
        ea._resolve_status(
            invalidated=True,
            missed=False,
            in_zone=False,
            mode_ok=False,
            triggers={},
            distance_pct=10,
            direction="LONG",
            score=80,
            phase="trending",
        )
        == "INVALIDATED"
    )
    assert (
        ea._resolve_status(
            invalidated=False,
            missed=True,
            in_zone=False,
            mode_ok=False,
            triggers={},
            distance_pct=12,
            direction="LONG",
            score=80,
            phase="expansion",
        )
        == "MISSED"
    )
