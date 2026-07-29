"""Market scanner pipeline: Bybit → engines → signals DB."""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.explanation import build_explanation
from app.config.settings import settings
from app.database.models import Candle, MarketEvent, Signal, Symbol
from app.engines.pump_detector.analyzer import PumpDetector
from app.engines.scoring.calculator import ScoreCalculator
from app.engines.structure.analyzer import StructureAnalyzer
from app.exchanges.bybit import BybitClient
from app.market_data.candles import CandleBar

logger = logging.getLogger(__name__)


class ScannerService:
    def __init__(self, client: Optional[BybitClient] = None):
        self.client = client or BybitClient()
        self.scorer = ScoreCalculator()
        self.pump = PumpDetector()
        self.structure = StructureAnalyzer()

    async def sync_symbols(self, db: AsyncSession, limit: Optional[int] = None) -> list[Symbol]:
        limit = limit or settings.scan_symbol_limit
        tickers = await self.client.get_tickers()
        # Rank by turnover24h
        ranked = sorted(
            tickers,
            key=lambda t: float(t.get("turnover24h") or 0),
            reverse=True,
        )
        selected = ranked[:limit]
        symbols: list[Symbol] = []
        for t in selected:
            sym = t.get("symbol")
            if not sym or not str(sym).endswith("USDT"):
                continue
            result = await db.execute(
                select(Symbol).where(Symbol.exchange == "bybit", Symbol.symbol == sym)
            )
            row = result.scalar_one_or_none()
            vol = float(t.get("turnover24h") or 0)
            if row is None:
                row = Symbol(
                    exchange="bybit",
                    symbol=sym,
                    market_type="linear",
                    volume_24h=vol,
                    active=True,
                )
                db.add(row)
            else:
                row.volume_24h = vol
                row.active = True
            symbols.append(row)
        await db.commit()
        for s in symbols:
            await db.refresh(s)
        return symbols

    async def fetch_and_store_candles(
        self,
        db: AsyncSession,
        symbol: Symbol,
        timeframe: str,
        limit: int = 200,
    ) -> list[CandleBar]:
        bars = await self.client.get_klines(symbol.symbol, timeframe=timeframe, limit=limit)
        from app.market_data.validation import filter_valid

        bars = filter_valid(bars)
        for bar in bars:
            stmt = (
                pg_insert(Candle)
                .values(
                    symbol_id=symbol.id,
                    timeframe=timeframe,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                    timestamp=bar.timestamp,
                )
                .on_conflict_do_update(
                    constraint="uq_candle",
                    set_={
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "volume": bar.volume,
                    },
                )
            )
            await db.execute(stmt)
        await db.commit()
        # Also write multi-exchange Timescale history
        try:
            from app.services.history_ingest import store_bars

            await store_bars(
                db,
                bars,
                exchange=getattr(symbol, "exchange", None) or "bybit",
                symbol=symbol.symbol,
                timeframe=timeframe,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("market_candles upsert skipped: %s", exc)
        return bars

    async def analyze_symbol(
        self,
        db: AsyncSession,
        symbol: Symbol,
        timeframe: str = "15",
    ) -> dict[str, Any]:
        bars = await self.fetch_and_store_candles(db, symbol, timeframe)
        htf_bars = await self.client.get_klines(symbol.symbol, timeframe="240", limit=120)
        htf_swings = self.structure.find_swings(htf_bars)
        htf_trend = self.structure.current_trend(htf_swings)

        oi_change = 0.0
        funding = None
        try:
            oi = await self.client.get_open_interest(symbol.symbol)
            if oi:
                oi_change = float(oi.get("oi_change_pct") or 0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("OI fetch failed for %s: %s", symbol.symbol, exc)
        try:
            funding = await self.client.get_funding_rate(symbol.symbol)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Funding fetch failed for %s: %s", symbol.symbol, exc)

        analysis = self.scorer.analyze_symbol(
            symbol=symbol.symbol,
            candles=bars,
            timeframe=timeframe,
            oi_change_pct=oi_change,
            funding=funding,
            htf_trend=htf_trend,
        )
        pump = self.pump.analyze(
            bars,
            oi_change_pct=oi_change,
            market_cap=symbol.market_cap,
        )
        analysis["pump"] = pump
        # Market intelligence enrichments
        from app.engines.regime.analyzer import MarketRegimeDetector
        from app.engines.anomaly.detector import AnomalyDetector
        from app.market_data.volume_intelligence import relative_volume_smart

        analysis["regime"] = MarketRegimeDetector().analyze(bars)
        analysis["anomaly"] = AnomalyDetector().analyze(bars, oi_change_pct=oi_change)
        analysis["volume_intelligence"] = relative_volume_smart(bars)
        analysis["explanation"] = build_explanation(analysis, pump)
        return analysis

    async def persist_analysis(self, db: AsyncSession, analysis: dict[str, Any]) -> Optional[Signal]:
        score = int(analysis.get("score") or 0)
        pump_score = int((analysis.get("pump") or {}).get("total") or 0)
        if score < settings.min_signal_score and pump_score < settings.min_signal_score:
            return None

        # Prefer higher of SMC vs pump presentation
        use_pump = pump_score >= score and pump_score >= settings.min_signal_score
        final_score = pump_score if use_pump else score
        signal_type = "pump" if use_pump else "smc"
        levels = analysis.get("levels") or {}

        # Deactivate older active signals for same exchange+symbol+tf
        await db.execute(
            delete(Signal).where(
                Signal.symbol == analysis["symbol"],
                Signal.exchange == (analysis.get("exchange") or "bybit"),
                Signal.timeframe == analysis["timeframe"],
                Signal.status == "active",
            )
        )

        reason = {
            **(analysis.get("reasons") or {}),
            "components": analysis.get("components"),
            "pump": analysis.get("pump"),
            "checklist": (analysis.get("reasons") or {}).get("checklist"),
            "regime": analysis.get("regime"),
            "anomaly": analysis.get("anomaly"),
            "volume_intelligence": analysis.get("volume_intelligence"),
            "market": analysis.get("market"),
            "setup_score": analysis.get("setup_score"),
            "execution_score": analysis.get("execution_score"),
            "overall_score": analysis.get("overall_score"),
            "probability": analysis.get("probability"),
            "lifecycle_status": analysis.get("lifecycle_status"),
            "timing": analysis.get("timing"),
            "edge_score": analysis.get("edge_score"),
            "edge_reasons": analysis.get("edge_reasons"),
            "score_history": analysis.get("score_history") or [],
            "replay": analysis.get("replay") or [],
            "progress": analysis.get("progress"),
            "next_steps": analysis.get("next_steps"),
            "ai_comment": analysis.get("ai_comment"),
            "phase_ru": analysis.get("phase_ru"),
            "risk_label": analysis.get("risk_label"),
            "tp1": levels.get("tp1"),
        }

        signal = Signal(
            symbol=analysis["symbol"],
            exchange=analysis.get("exchange") or "bybit",
            direction=analysis.get("direction") or "LONG",
            signal_type=signal_type,
            score=final_score,
            confidence=analysis.get("confidence") or "medium",
            timeframe=analysis.get("timeframe") or "15",
            entry=levels.get("entry"),
            stop=levels.get("stop"),
            target=levels.get("tp2"),
            risk_reward=levels.get("risk_reward"),
            risk_pct=levels.get("risk_pct"),
            reason=reason,
            zones=analysis.get("zones") or {},
            explanation=analysis.get("ai_comment") or analysis.get("explanation"),
            status="active",
        )
        db.add(signal)

        # Store key events
        for sweep in (analysis.get("zones") or {}).get("liquidity_sweeps") or []:
            db.add(
                MarketEvent(
                    symbol=analysis["symbol"],
                    event_type="liquidity_sweep",
                    timeframe=analysis["timeframe"],
                    price=sweep.get("price"),
                    strength=sweep.get("strength"),
                    event_metadata=sweep,
                )
            )
        await db.commit()
        await db.refresh(signal)

        # Part 8: notify high/elite
        try:
            from app.notifications.manager import NotificationManager

            await NotificationManager().handle_signal(db, signal)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Notification skipped: %s", exc)
        return signal

    async def run_scan(
        self,
        db: AsyncSession,
        timeframe: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[Signal]:
        timeframe = timeframe or settings.timeframe_list[0]
        symbols = await self.sync_symbols(db, limit=limit)
        created: list[Signal] = []
        for sym in symbols:
            try:
                analysis = await self.analyze_symbol(db, sym, timeframe=timeframe)
                signal = await self.persist_analysis(db, analysis)
                if signal:
                    created.append(signal)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Scan failed for %s: %s", sym.symbol, exc)
        logger.info("Scan complete: %d signals from %d symbols", len(created), len(symbols))
        return created

    async def run_scan_memory(
        self,
        timeframe: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Live scan without PostgreSQL — results go to memory_store."""
        from app.services import memory_store

        timeframe = timeframe or settings.timeframe_list[0]
        limit = limit or settings.scan_symbol_limit
        tickers = await self.client.get_tickers()
        ranked = sorted(tickers, key=lambda t: float(t.get("turnover24h") or 0), reverse=True)
        selected = [
            t
            for t in ranked
            if (t.get("symbol") or "").endswith("USDT")
        ][:limit]

        created: list[dict[str, Any]] = []
        for t in selected:
            sym = t["symbol"]
            try:
                analysis = await self.analyze_symbol_live(
                    sym,
                    timeframe=timeframe,
                    market_cap=None,
                    volume_24h=float(t.get("turnover24h") or 0),
                )
                row = self._analysis_to_signal_dict(analysis)
                if row:
                    memory_store.upsert_signal(row)
                    created.append(row)
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                if "Symbol Is Invalid" in msg or "10001" in msg:
                    logger.warning("Skip invalid Bybit symbol %s", sym)
                else:
                    logger.warning("Memory scan failed for %s: %s", sym, msg)
        logger.info("Memory scan complete: %d signals from %d symbols", len(created), len(selected))
        return created

    async def analyze_symbol_live(
        self,
        symbol: str,
        timeframe: str = "15",
        market_cap: Optional[float] = None,
        volume_24h: float = 0.0,
    ) -> dict[str, Any]:
        from app.market_data.validation import filter_valid

        bars = filter_valid(await self.client.get_klines(symbol, timeframe=timeframe, limit=200))
        htf_bars = await self.client.get_klines(symbol, timeframe="240", limit=120)
        htf_swings = self.structure.find_swings(htf_bars)
        htf_trend = self.structure.current_trend(htf_swings)

        oi_change = 0.0
        funding = None
        try:
            oi = await self.client.get_open_interest(symbol)
            if oi:
                oi_change = float(oi.get("oi_change_pct") or 0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("OI fetch failed for %s: %s", symbol, exc)
        try:
            funding = await self.client.get_funding_rate(symbol)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Funding fetch failed for %s: %s", symbol, exc)

        analysis = self.scorer.analyze_symbol(
            symbol=symbol,
            candles=bars,
            timeframe=timeframe,
            oi_change_pct=oi_change,
            funding=funding,
            htf_trend=htf_trend,
        )
        analysis["exchange"] = "bybit"
        pump = self.pump.analyze(bars, oi_change_pct=oi_change, market_cap=market_cap)
        analysis["pump"] = pump
        from app.engines.regime.analyzer import MarketRegimeDetector
        from app.engines.anomaly.detector import AnomalyDetector
        from app.market_data.volume_intelligence import relative_volume_smart

        analysis["regime"] = MarketRegimeDetector().analyze(bars)
        analysis["anomaly"] = AnomalyDetector().analyze(bars, oi_change_pct=oi_change)
        analysis["volume_intelligence"] = relative_volume_smart(bars)
        analysis["market"] = {"volume_24h": volume_24h}
        analysis["explanation"] = build_explanation(analysis, pump)
        return analysis

    def _analysis_to_signal_dict(self, analysis: dict[str, Any]) -> Optional[dict[str, Any]]:
        score = int(analysis.get("score") or 0)
        pump_score = int((analysis.get("pump") or {}).get("total") or 0)
        if score < settings.min_signal_score and pump_score < settings.min_signal_score:
            return None
        use_pump = pump_score >= score and pump_score >= settings.min_signal_score
        final_score = pump_score if use_pump else score
        levels = analysis.get("levels") or {}
        reason = {
            **(analysis.get("reasons") or {}),
            "components": analysis.get("components"),
            "pump": analysis.get("pump"),
            "regime": analysis.get("regime"),
            "anomaly": analysis.get("anomaly"),
            "volume_intelligence": analysis.get("volume_intelligence"),
            "market": {
                **(analysis.get("market") or {}),
                "current_price": analysis.get("current_price")
                or (analysis.get("levels") or {}).get("entry"),
            },
            "setup_score": analysis.get("setup_score"),
            "execution_score": analysis.get("execution_score"),
            "overall_score": analysis.get("overall_score"),
            "probability": analysis.get("probability"),
            "lifecycle_status": analysis.get("lifecycle_status"),
            "waiting_for": analysis.get("waiting_for"),
            "progress": analysis.get("progress"),
            "next_steps": analysis.get("next_steps"),
            "ai_comment": analysis.get("ai_conclusion") or analysis.get("ai_comment"),
            "ai_conclusion": analysis.get("ai_conclusion"),
            "zone_note": analysis.get("zone_note"),
            "why_no_entry": analysis.get("why_no_entry"),
            "invalidation": analysis.get("invalidation") or [],
            "confidence_drivers": analysis.get("confidence_drivers") or [],
            "next_trigger": analysis.get("next_trigger"),
            "range_scale": analysis.get("range_scale"),
            "scenario_probability": analysis.get("scenario_probability"),
            "entry_probability_now": analysis.get("entry_probability_now"),
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
            "edge_score": analysis.get("edge_score"),
            "edge_stars": analysis.get("edge_stars"),
            "edge_reasons": analysis.get("edge_reasons") or [],
            "edge_hint": analysis.get("edge_hint"),
            "replay": analysis.get("replay") or [],
            "score_history": analysis.get("score_history") or [],
            "phase_ru": analysis.get("phase_ru"),
            "risk_label": analysis.get("risk_label"),
            "scenario_risk_pct": analysis.get("scenario_risk_pct"),
            "action": analysis.get("action"),
            "tp1": levels.get("tp1"),
        }
        return {
            "symbol": analysis["symbol"],
            "exchange": analysis.get("exchange") or "bybit",
            "direction": analysis.get("direction") or "LONG",
            "signal_type": "pump" if use_pump else "smc",
            "score": final_score,
            "confidence": analysis.get("confidence") or "medium",
            "timeframe": analysis.get("timeframe") or "15",
            "entry": levels.get("entry"),
            "stop": levels.get("stop"),
            "target": levels.get("tp2"),
            "risk_reward": levels.get("risk_reward"),
            "risk_pct": levels.get("risk_pct"),
            "reason": reason,
            "zones": analysis.get("zones") or {},
            "explanation": analysis.get("ai_conclusion") or analysis.get("explanation"),
            "status": "active",
            "setup_score": analysis.get("setup_score"),
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
            "progress": analysis.get("progress") or [],
            "waiting_for": analysis.get("waiting_for") or [],
            "next_steps": analysis.get("next_steps") or [],
            "ai_comment": analysis.get("ai_conclusion") or analysis.get("ai_comment"),
            "ai_conclusion": analysis.get("ai_conclusion"),
            "zone_note": analysis.get("zone_note"),
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
            "edge_score": analysis.get("edge_score"),
            "edge_stars": analysis.get("edge_stars"),
            "edge_reasons": analysis.get("edge_reasons") or [],
            "edge_hint": analysis.get("edge_hint"),
            "replay": analysis.get("replay") or [],
            "score_history": analysis.get("score_history") or [],
            "risk_label": analysis.get("risk_label"),
            "scenario_risk_pct": analysis.get("scenario_risk_pct"),
            "current_price": analysis.get("current_price") or levels.get("entry"),
            "distance_pct": analysis.get("distance_pct"),
            "distance_label": analysis.get("distance_label"),
            "action": analysis.get("action"),
            "freshness": analysis.get("freshness"),
            "freshness_ru": analysis.get("freshness_ru"),
            "age_sec": analysis.get("age_sec"),
            "age_label": analysis.get("age_label"),
            "reeval_sec": 60,
            "tp1": levels.get("tp1"),
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
            "ai_verdict": analysis.get("ai_verdict"),
        }
