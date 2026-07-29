"""Backtesting engine — SMC sequence replay (Part 6 MVP)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.backtesting.data_loader import load_candles
from app.backtesting.metrics import compute_metrics
from app.backtesting.simulator import EntryModel, SimulatedTrade, simulate_trade
from app.engines.scoring.calculator import ScoreCalculator
from app.engines.pump_detector.analyzer import PumpDetector
from app.market_data.candles import CandleBar

TF_MINUTES = {"1": 1, "3": 3, "5": 5, "15": 15, "30": 30, "60": 60, "240": 240, "D": 1440}


class BacktestEngine:
    def __init__(self):
        self.scorer = ScoreCalculator()
        self.pump = PumpDetector()

    async def run(
        self,
        db: AsyncSession,
        *,
        symbol: str,
        timeframe: str = "15",
        strategy: Literal["smc", "pump", "sweep_fvg"] = "smc",
        limit: int = 800,
        min_score: int = 75,
        entry_model: EntryModel = "aggressive",
        risk_pct: float = 1.0,
    ) -> dict[str, Any]:
        candles = await load_candles(db, symbol, timeframe=timeframe, limit=limit)
        if len(candles) < 80:
            return {
                "symbol": symbol,
                "strategy": strategy,
                "error": "insufficient_history",
                "metrics": compute_metrics([]),
                "trades": [],
            }

        trades: list[SimulatedTrade] = []
        trade_logs: list[dict[str, Any]] = []
        step = 5
        warmup = 60
        tf_min = TF_MINUTES.get(timeframe, 15)
        cooldown_until = 0

        for i in range(warmup, len(candles) - 10, step):
            if i < cooldown_until:
                continue
            window = candles[: i + 1]
            if strategy == "pump":
                pump = self.pump.analyze(window)
                if pump["total"] < min_score:
                    continue
                analysis = self.scorer.analyze_symbol(symbol, window, timeframe=timeframe)
                analysis["score"] = pump["total"]
                analysis["signal_type"] = "pump"
            else:
                analysis = self.scorer.analyze_symbol(symbol, window, timeframe=timeframe)
                if analysis["score"] < min_score:
                    continue
                if strategy == "sweep_fvg":
                    cl = analysis.get("reasons", {}).get("checklist", {})
                    if not (cl.get("liquidity_sweep") and cl.get("fvg")):
                        continue
                if not analysis.get("sequence_valid") and strategy == "smc":
                    # allow medium quality but prefer sequence
                    if analysis["score"] < min_score + 5:
                        continue

            levels = analysis.get("levels") or {}
            entry = levels.get("entry")
            stop = levels.get("stop")
            target = levels.get("tp2") or levels.get("tp1")
            if not entry or not stop or not target:
                continue

            sim = simulate_trade(
                candles,
                entry=entry,
                stop=stop,
                target=target,
                direction=analysis.get("direction") or "LONG",
                entry_model=entry_model,
                start_index=i,
                timeframe_minutes=tf_min,
            )
            trades.append(sim)
            trade_logs.append(
                {
                    "index": i,
                    "timestamp": window[-1].timestamp,
                    "direction": analysis.get("direction"),
                    "score": analysis.get("score"),
                    "result": sim.result,
                    "rr": round(sim.rr, 2),
                    "time_in_trade": sim.time_in_trade,
                }
            )
            cooldown_until = i + max(3, sim.bars_held)

        metrics = compute_metrics(trades)
        equity_curve = []
        eq = 0.0
        for t in trades:
            if t.result in ("WIN", "LOSS"):
                eq += t.rr
                equity_curve.append(round(eq, 2))

        return {
            "symbol": symbol.upper(),
            "strategy": strategy,
            "timeframe": timeframe,
            "candles_used": len(candles),
            "entry_model": entry_model,
            "risk_pct": risk_pct,
            "min_score": min_score,
            "metrics": metrics,
            "equity_curve": equity_curve,
            "trades": trade_logs[-100:],
            "disclaimer": "Historical simulation only. Not predictive of future results.",
        }
