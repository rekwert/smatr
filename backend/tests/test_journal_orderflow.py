"""Tests for journal stats and tape orderflow."""

from __future__ import annotations

import pytest

from app.engines.inefficiency.orderflow import delta_from_trades
from app.services import journal as journal_svc


def test_delta_favors_buy_for_long():
    trades = [
        {"side": "buy", "size": 10, "price": 100},
        {"side": "buy", "size": 8, "price": 100},
        {"side": "sell", "size": 3, "price": 100},
    ]
    d = delta_from_trades(trades, direction="LONG")
    assert d["imbalance"] > 0
    assert d["score"] >= 55


def test_delta_favors_sell_for_short():
    trades = [
        {"side": "sell", "size": 12, "price": 50},
        {"side": "buy", "size": 2, "price": 50},
    ]
    d = delta_from_trades(trades, direction="SHORT")
    assert d["aligned"] > 0
    assert d["score"] >= 55


@pytest.mark.asyncio
async def test_journal_winrate_after_trades():
    journal_svc._MEM.clear()
    await journal_svc.create_trade(symbol="AAAUSDT", direction="LONG", result="win", result_r=1.5)
    await journal_svc.create_trade(symbol="BBBUSDT", direction="LONG", result="win", result_r=2.0)
    await journal_svc.create_trade(symbol="CCCUSDT", direction="SHORT", result="loss", result_r=-1.0)
    await journal_svc.create_trade(symbol="DDDUSDT", direction="LONG", result="win", result_r=1.0)
    await journal_svc.create_trade(symbol="EEEUSDT", direction="LONG", result="loss", result_r=-1.0)
    stats = await journal_svc.journal_stats(setup="inefficiency")
    assert stats["closed"] == 5
    assert stats["wins"] == 3
    assert stats["winrate"] == 60.0
    assert stats["usable_for_edge"] is True
