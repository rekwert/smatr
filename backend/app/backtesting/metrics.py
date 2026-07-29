"""Backtest statistics (Part 6 / 17)."""

from __future__ import annotations

import math
from typing import Sequence

from app.backtesting.simulator import SimulatedTrade


def compute_metrics(trades: Sequence[SimulatedTrade]) -> dict:
    closed = [t for t in trades if t.result in ("WIN", "LOSS")]
    if not closed:
        return {
            "trades": 0,
            "winrate": 0.0,
            "average_rr": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "max_drawdown_r": 0.0,
            "sharpe": 0.0,
            "open_trades": len([t for t in trades if t.result == "OPEN"]),
        }

    wins = [t for t in closed if t.result == "WIN"]
    losses = [t for t in closed if t.result == "LOSS"]
    winrate = len(wins) / len(closed) * 100
    avg_win = sum(t.rr for t in wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(t.rr for t in losses) / len(losses)) if losses else 1.0
    gross_profit = sum(t.rr for t in wins)
    gross_loss = abs(sum(t.rr for t in losses)) or 1e-9
    profit_factor = gross_profit / gross_loss
    expectancy = (winrate / 100) * avg_win - ((100 - winrate) / 100) * avg_loss

    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    returns = []
    for t in closed:
        equity += t.rr
        returns.append(t.rr)
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    sharpe = 0.0
    if len(returns) >= 2:
        mean = sum(returns) / len(returns)
        var = sum((x - mean) ** 2 for x in returns) / (len(returns) - 1)
        std = math.sqrt(var) if var > 0 else 0.0
        if std > 0:
            sharpe = mean / std * math.sqrt(len(returns))

    return {
        "trades": len(closed),
        "winrate": round(winrate, 2),
        "average_rr": round(sum(t.rr for t in closed) / len(closed), 2),
        "avg_win_r": round(avg_win, 2),
        "avg_loss_r": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2),
        "expectancy": round(expectancy, 2),
        "max_drawdown_r": round(max_dd, 2),
        "sharpe": round(sharpe, 2),
        "open_trades": len([t for t in trades if t.result == "OPEN"]),
    }
