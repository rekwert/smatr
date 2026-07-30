"""Level 3 — Heavy Analysis (SMC + AI) on shortlist only."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from app.engines.scoring.calculator import ScoreCalculator
from app.engines.pump_detector.analyzer import PumpDetector
from app.exchange_layer.market_data_engine import MarketDataEngine
from app.ml.decision import decide
from app.ml.features import extract_features
from app.ml.models import run_quant_models
from app.universe.models import HeavyCandidate, UniverseRow

logger = logging.getLogger(__name__)


async def heavy_analyze(
    candidates: list[UniverseRow],
    *,
    limit: int = 80,
    concurrency: int = 6,
    timeframe: str = "15m",
) -> list[HeavyCandidate]:
    """Run SMC + Quant on top cheap-filter candidates."""
    mde = MarketDataEngine()
    scorer = ScoreCalculator()
    pump = PumpDetector()
    sem = asyncio.Semaphore(concurrency)
    selected = candidates[:limit]
    results: list[HeavyCandidate] = []

    similar_winrate = None
    try:
        from app.services.journal import journal_stats

        stats = await journal_stats(setup="inefficiency")
        if stats.get("usable_for_edge") and stats.get("winrate") is not None:
            similar_winrate = float(stats["winrate"])
    except Exception as exc:  # noqa: BLE001
        logger.debug("journal stats skip: %s", exc)

    async def _one(row: UniverseRow) -> Optional[HeavyCandidate]:
        async with sem:
            try:
                bars = await mde.get_candles_as_bars(
                    row.symbol, timeframe, exchange=row.exchange, limit=120
                )
                if len(bars) < 40:
                    return None
                # Best-effort history write (Timescale)
                try:
                    from app.database.connection import SessionLocal
                    from app.services.history_ingest import store_bars, store_derivatives

                    async with SessionLocal() as db:
                        await store_bars(
                            db,
                            bars,
                            exchange=row.exchange,
                            symbol=row.symbol,
                            timeframe="15",
                        )
                        await store_derivatives(
                            db,
                            exchange=row.exchange,
                            symbol=row.symbol,
                            open_interest=float(row.open_interest)
                            if row.open_interest is not None
                            else None,
                            funding_rate=float(row.funding_rate)
                            if row.funding_rate is not None
                            else None,
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("history write skip %s/%s: %s", row.exchange, row.symbol, exc)
                oi_chg = 0.0
                funding = row.funding_rate
                orderflow_override = None
                try:
                    oi = await mde.get_adapter(row.exchange).get_open_interest(row.symbol)
                    if oi:
                        oi_chg = float(oi.get("oi_change_pct") or 0)
                except Exception:  # noqa: BLE001
                    pass
                try:
                    from app.engines.inefficiency.orderflow import delta_from_trades

                    trades = await mde.get_adapter(row.exchange).get_recent_trades(
                        row.symbol, limit=80
                    )
                    # Direction unknown yet — score both; analyzer will prefer after infer
                    # Use neutral LONG first; recalculated after analyze if needed
                    delta = delta_from_trades(trades, direction="LONG")
                    if delta.get("sample", 0) >= 20:
                        orderflow_override = float(delta["score"])
                except Exception:  # noqa: BLE001
                    pass

                analysis = scorer.analyze_symbol(
                    symbol=row.symbol,
                    candles=bars,
                    timeframe="15",
                    oi_change_pct=oi_chg,
                    funding=funding,
                    volume_24h=float(row.volume_24h or 0) or None,
                    similar_winrate=similar_winrate,
                    orderflow_override=orderflow_override,
                )
                # Re-align tape delta to final direction if we have trades
                if orderflow_override is not None:
                    try:
                        from app.engines.inefficiency.orderflow import delta_from_trades

                        trades = await mde.get_adapter(row.exchange).get_recent_trades(
                            row.symbol, limit=80
                        )
                        d2 = delta_from_trades(
                            trades, direction=str(analysis.get("direction") or "LONG")
                        )
                        if d2.get("sample", 0) >= 20:
                            comps = analysis.get("components") or {}
                            comps["orderflow"] = float(d2["score"])
                            comps["tape_imbalance"] = float(d2.get("imbalance") or 0)
                            analysis["components"] = comps
                            analysis["relative_volume"] = analysis.get("relative_volume")
                            analysis["orderflow_tape"] = d2
                    except Exception:  # noqa: BLE001
                        pass

                pump_a = pump.analyze(bars, oi_change_pct=oi_chg)
                features = extract_features(
                    row.symbol,
                    bars,
                    oi_change=oi_chg,
                    funding=funding,
                    spread_pct=row.spread_pct,
                )
                q = run_quant_models(features)
                decision = decide(
                    quant=q,
                    smc_score=float(analysis.get("score") or 0),
                    hunter_score=float(pump_a.get("total") or 0),
                    liquidity_score=row.liquidity_score,
                )
                smc = float(analysis.get("score") or 0)
                final = int(
                    round(
                        0.35 * decision["ai_score"]
                        + 0.30 * smc
                        + 0.20 * float(pump_a.get("total") or 0)
                        + 0.15 * row.cheap_score
                    )
                )
                reasons = list(row.reasons)[:4]
                found = (analysis.get("reasons") or {}).get("found") or []
                reasons.extend(found[:4])
                if oi_chg:
                    reasons.append(f"OI {oi_chg:+.1f}%")
                levels = analysis.get("levels") or {}
                return HeavyCandidate(
                    exchange=row.exchange,
                    symbol=row.symbol,
                    score=min(100, final),
                    direction=str(analysis.get("direction") or q.get("preferred_direction") or "LONG"),
                    tier=row.tier,
                    cheap_score=row.cheap_score,
                    smc_score=smc,
                    ai_score=float(decision["ai_score"]),
                    pump_probability_pct=float(decision["pump_probability_pct"]),
                    risk_level=str(decision["risk_level"]),
                    reasons=reasons[:8],
                    liquidity_score=row.liquidity_score,
                    volume_24h=row.volume_24h,
                    oi_change_pct=oi_chg,
                    funding=float(funding) if funding is not None else None,
                    entry=levels.get("entry") or analysis.get("ideal_entry") or analysis.get("current_price"),
                    stop=levels.get("stop") or analysis.get("stop"),
                    target=levels.get("tp2") or analysis.get("tp2"),
                    analysis=analysis,
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("heavy skip %s/%s: %s", row.exchange, row.symbol, exc)
                return None

    raw = await asyncio.gather(*[_one(c) for c in selected])
    results = [r for r in raw if r]
    results.sort(key=lambda x: x.score, reverse=True)
    return results
