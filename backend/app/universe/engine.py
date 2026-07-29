"""Universe Engine orchestrator — 3 levels + cross-exchange."""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.services import memory_store
from app.universe.cheap_filter import apply_cheap_filter
from app.universe.collector import collect_universe, universe_stats
from app.universe.cross_exchange import find_cross_inefficiencies
from app.universe.heavy import heavy_analyze
from app.universe.store import save_snapshot

logger = logging.getLogger(__name__)


class UniverseEngine:
    """
    6 Exchanges → ALL Futures → Liquidity/Volume filter
    → SMC Engine → AI Ranking → Trade ideas
    """

    async def run(
        self,
        *,
        exchanges: Optional[list[str]] = None,
        cheap_limit: int = 200,
        heavy_limit: int = 80,
        trade_ideas: int = 15,
        do_heavy: bool = True,
        persist_memory: bool = True,
    ) -> dict[str, Any]:
        # Level 1
        universe = await collect_universe(exchanges)
        stats = universe_stats(universe)
        logger.info("L1 universe total=%s unique=%s", stats["total"], stats["unique_symbols"])

        # Level 2
        cheap = apply_cheap_filter(universe, max_candidates=cheap_limit)
        logger.info("L2 cheap filter → %d candidates", len(cheap))

        # Cross-exchange (on full universe, not only cheap)
        cross = find_cross_inefficiencies(universe, limit=40)

        # Level 3
        heavy_rows = []
        if do_heavy and cheap:
            heavy_rows = await heavy_analyze(cheap, limit=heavy_limit)
            logger.info("L3 heavy → %d scored", len(heavy_rows))

        ideas = heavy_rows[:trade_ideas]
        payload = {
            "pipeline": "Market Universe Engine v2",
            "stats": stats,
            "levels": {
                "l1_universe": stats["total"],
                "l2_cheap": len(cheap),
                "l3_heavy": len(heavy_rows),
                "trade_ideas": len(ideas),
            },
            "tiers": {
                "A_medium_liq": sum(1 for c in cheap if c.tier == "A"),
                "B_low_liq": sum(1 for c in cheap if c.tier == "B"),
                "C_new_listings": sum(1 for c in cheap if c.tier == "C"),
            },
            "cheap": [c.to_dict() for c in cheap[:100]],
            "heavy": [h.to_dict() for h in heavy_rows[:50]],
            "trade_ideas": [h.to_dict() for h in ideas],
            "cross_exchange": [c.to_dict() for c in cross],
            "disclaimer": "Аналитика. Не финансовый совет. Автоторговля отключена.",
        }

        save_snapshot(
            stats=stats,
            cheap=payload["cheap"],
            heavy=payload["heavy"],
            cross=payload["cross_exchange"],
            trade_ideas=payload["trade_ideas"],
        )

        if persist_memory:
            from app.services.history_ingest import persist_signal_row
            from app.database.connection import SessionLocal
            import socket

            def _pg_up() -> bool:
                try:
                    with socket.create_connection(("127.0.0.1", 5433), timeout=0.4):
                        return True
                except OSError:
                    return False

            pg_ok = _pg_up()

            for h in ideas:
                if h.score < 50:
                    continue
                analysis = h.analysis or {}
                levels = analysis.get("levels") or {}
                reasons_block = {
                    **(analysis.get("reasons") or {}),
                    "found": h.reasons,
                    "components": analysis.get("components"),
                    "universe_v2": True,
                    "tier": h.tier,
                    "ai_score": h.ai_score,
                    "smc_score": h.smc_score,
                    "pump_probability_pct": h.pump_probability_pct,
                    "risk_level": h.risk_level,
                    "liquidity_score": h.liquidity_score,
                    "market": {
                        "volume_24h": h.volume_24h,
                        "current_price": analysis.get("current_price") or h.entry,
                    },
                    "setup_score": analysis.get("setup_score"),
                    "execution_score": analysis.get("execution_score"),
                    "overall_score": analysis.get("overall_score"),
                    "probability": analysis.get("probability"),
                    "lifecycle_status": analysis.get("lifecycle_status"),
                    "waiting_for": analysis.get("waiting_for"),
                    "ai_conclusion": analysis.get("ai_conclusion"),
                    "tp1": levels.get("tp1") or analysis.get("tp1"),
                }
                signal_row = {
                    "symbol": h.symbol,
                    "exchange": h.exchange,
                    "direction": h.direction,
                    "signal_type": "smc",
                    "score": int(analysis.get("setup_score") or h.score),
                    "confidence": "high" if h.score >= 85 else "medium" if h.score >= 70 else "low",
                    "timeframe": "15",
                    "entry": analysis.get("ideal_entry") or h.entry or levels.get("entry"),
                    "stop": h.stop or levels.get("stop") or analysis.get("stop"),
                    "target": h.target or levels.get("tp2") or analysis.get("tp2"),
                    "risk_reward": levels.get("risk_reward") or analysis.get("risk_reward"),
                    "risk_pct": levels.get("risk_pct"),
                    "reason": reasons_block,
                    "zones": analysis.get("zones") or {},
                    "explanation": analysis.get("ai_conclusion") or analysis.get("explanation"),
                    "status": "active",
                    "setup_score": analysis.get("setup_score") or h.smc_score,
                    "execution_score": analysis.get("execution_score"),
                    "overall_score": analysis.get("overall_score"),
                    "overall_formula": analysis.get("overall_formula"),
                    "setup_stars": analysis.get("setup_stars"),
                    "execution_stars": analysis.get("execution_stars"),
                    "probability": analysis.get("probability"),
                    "scenario_probability": analysis.get("scenario_probability"),
                    "entry_probability_now": analysis.get("entry_probability_now"),
                    "lifecycle_status": analysis.get("lifecycle_status"),
                    "lifecycle_emoji": analysis.get("lifecycle_emoji"),
                    "lifecycle_ru": analysis.get("lifecycle_ru"),
                    "lifecycle_hint": analysis.get("lifecycle_hint"),
                    "phase": analysis.get("phase"),
                    "phase_ru": analysis.get("phase_ru"),
                    "waiting_for": analysis.get("waiting_for") or [],
                    "next_steps": analysis.get("next_steps") or [],
                    "ai_comment": analysis.get("ai_conclusion"),
                    "ai_conclusion": analysis.get("ai_conclusion"),
                    "ai_verdict": analysis.get("ai_verdict"),
                    "why_no_entry": analysis.get("why_no_entry"),
                    "invalidation": analysis.get("invalidation") or [],
                    "confidence_drivers": analysis.get("confidence_drivers") or [],
                    "next_trigger": analysis.get("next_trigger"),
                    "range_scale": analysis.get("range_scale"),
                    "liquidity_quality": analysis.get("liquidity_quality"),
                    "liquidity_stars": analysis.get("liquidity_stars"),
                    "liquidity_hint": analysis.get("liquidity_hint"),
                    "chasing_risk": analysis.get("chasing_risk"),
                    "chasing_level": analysis.get("chasing_level"),
                    "chasing_level_ru": analysis.get("chasing_level_ru"),
                    "chasing_hint": analysis.get("chasing_hint"),
                    "smart_money_activity": analysis.get("smart_money_activity"),
                    "smart_money_ru": analysis.get("smart_money_ru"),
                    "smart_money_score": analysis.get("smart_money_score"),
                    "smart_money_stars": analysis.get("smart_money_stars"),
                    "smart_money_hint": analysis.get("smart_money_hint"),
                    "risk_label": analysis.get("risk_label"),
                    "scenario_risk_pct": analysis.get("scenario_risk_pct"),
                    "current_price": analysis.get("current_price") or h.entry,
                    "distance_pct": analysis.get("distance_pct"),
                    "distance_label": analysis.get("distance_label"),
                    "action": analysis.get("action"),
                    "timing": analysis.get("timing"),
                    "timing_emoji": analysis.get("timing_emoji"),
                    "timing_ru": analysis.get("timing_ru"),
                    "timing_reason": analysis.get("timing_reason"),
                    "traffic_lights": analysis.get("traffic_lights"),
                    "execution_breakdown": analysis.get("execution_breakdown"),
                    "ideal_entry": analysis.get("ideal_entry"),
                    "ideal_entry_low": analysis.get("ideal_entry_low"),
                    "ideal_entry_high": analysis.get("ideal_entry_high"),
                    "pd_zone": analysis.get("pd_zone"),
                    "edge_score": analysis.get("edge_score"),
                    "edge_reasons": analysis.get("edge_reasons"),
                    "score_history": analysis.get("score_history") or [],
                    "replay": analysis.get("replay") or [],
                    "tp1": levels.get("tp1") or analysis.get("tp1"),
                    "reeval_sec": 60,
                }
                memory_store.upsert_signal(signal_row)

                if pg_ok:
                    try:
                        async with SessionLocal() as db:
                            await persist_signal_row(db, signal_row)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("universe DB persist failed %s/%s: %s", h.exchange, h.symbol, exc)

        return payload
