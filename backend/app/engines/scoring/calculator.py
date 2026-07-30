"""Unified Score Engine — sequence-aware (Part 2 §1, §11–12)."""

from __future__ import annotations

from typing import Any, Optional, Sequence

from app.config.constants import (
    DEFAULT_SMC_WEIGHTS,
    SCORE_TIER_MEDIUM,
    SCORE_TIER_STRONG,
    SCORE_TIER_WEAK,
)
from app.engines.fvg.analyzer import FVGAnalyzer
from app.engines.liquidity.analyzer import LiquidityAnalyzer
from app.engines.order_blocks.analyzer import OrderBlockAnalyzer, PremiumDiscountAnalyzer
from app.engines.scoring.readiness import build_readiness_payload
from app.engines.structure.analyzer import StructureAnalyzer
from app.engines.types import EngineEvent
from app.engines.volume.analyzer import VolumeAnalyzer
from app.market_data.candles import CandleBar, atr


class ScoreCalculator:
    def __init__(self, weights: Optional[dict[str, int]] = None):
        self.weights = weights or dict(DEFAULT_SMC_WEIGHTS)
        self.structure = StructureAnalyzer()
        self.liquidity = LiquidityAnalyzer()
        self.fvg = FVGAnalyzer()
        self.order_blocks = OrderBlockAnalyzer()
        self.premium = PremiumDiscountAnalyzer()
        self.volume = VolumeAnalyzer()

    def analyze_symbol(
        self,
        symbol: str,
        candles: Sequence[CandleBar],
        timeframe: str = "15",
        oi_change_pct: float = 0.0,
        funding: Optional[float] = None,
        htf_trend: str = "range",
        volume_24h: Optional[float] = None,
    ) -> dict[str, Any]:
        if len(candles) < 30:
            return self._empty(symbol, timeframe, "Insufficient history")

        swings = self.structure.find_swings(candles)
        trend = self.structure.current_trend(swings)
        bos = self.structure.detect_bos(candles, swings)
        choch = self.structure.detect_choch(candles, swings)
        sweeps = self.liquidity.detect_sweep(candles, swings)
        equal_h = self.liquidity.find_equal_highs(candles)
        equal_l = self.liquidity.find_equal_lows(candles)
        fvgs = self.fvg.detect(candles)
        obs_bull = self.order_blocks.find_bullish_ob(candles, bos)
        obs_bear = self.order_blocks.find_bearish_ob(candles, bos)
        pd = self.premium.analyze(candles)
        vol = self.volume.analyze(candles)

        # Sequence logic: prefer aligned chain
        direction = self._infer_direction(sweeps, bos, choch, fvgs, pd, trend, htf_trend)
        components = self._component_scores(
            direction=direction,
            sweeps=sweeps,
            bos=bos,
            choch=choch,
            fvgs=fvgs,
            obs_bull=obs_bull,
            obs_bear=obs_bear,
            vol=vol,
            oi_change_pct=oi_change_pct,
            trend=trend,
            htf_trend=htf_trend,
            pd=pd,
            candles=candles,
        )

        legacy_score = self._weighted_total(components)
        sequence_valid = self._sequence_valid(components, direction)
        checklist = {
            "liquidity_sweep": components["liquidity_sweep"] >= 50,
            "fvg": components["fvg"] >= 50,
            "order_block": components["order_block"] >= 50,
            "oi": components["oi"] >= 50,
            "orderflow": components.get("orderflow", 0) >= 50,
            "volume": components["volume"] >= 50,
            "impulse_speed": components.get("impulse_speed", 0) >= 55,
            "post_impulse": components.get("post_impulse", 0) >= 55,
            "bos": components["bos"] >= 50,
            "htf_trend": components["htf_trend"] >= 50,
        }
        levels = self._trade_levels(candles, direction, sweeps, fvgs, obs_bull, obs_bear)
        current_px = float(candles[-1].close)
        zones = {
            "swings": [e.to_dict() for e in swings[-8:]],
            "liquidity_sweeps": [e.to_dict() for e in sweeps],
            "equal_highs": [e.to_dict() for e in equal_h[:3]],
            "equal_lows": [e.to_dict() for e in equal_l[:3]],
            "fvg": [e.to_dict() for e in fvgs[:4]],
            "order_blocks": [e.to_dict() for e in (obs_bull + obs_bear)[:4]],
            "premium_discount": pd,
            "bos": [e.to_dict() for e in bos],
            "choch": [e.to_dict() for e in choch],
        }
        readiness = build_readiness_payload(
            direction=direction,
            components=components,
            checklist=checklist,
            sequence_valid=sequence_valid,
            pd=pd,
            zones=zones,
            entry=levels.get("entry"),
            current_price=current_px,
            tp1=levels.get("tp1"),
            tp2=levels.get("tp2"),
            stop=levels.get("stop"),
            risk_reward=levels.get("risk_reward"),
            volume_24h=volume_24h,
        )
        # Public score = Setup Score (качество идеи), не смешанный legacy.
        score = int(readiness["setup_score"])
        tier = self.classify(score)
        reasons_found = list(readiness["confirmed"])
        reasons_missing = list(readiness["missing_items"])
        # Prefer Ideal Entry plan (Stop/TP already normalized in readiness)
        if readiness.get("ideal_entry") is not None:
            levels = {
                **levels,
                "entry": readiness.get("entry") or readiness["ideal_entry"],
                "ideal_entry": readiness["ideal_entry"],
                "stop": readiness.get("stop") or levels.get("stop"),
                "tp1": readiness.get("tp1") or levels.get("tp1"),
                "tp2": readiness.get("tp2") or levels.get("tp2"),
                "risk_reward": readiness.get("risk_reward") or levels.get("risk_reward"),
                "risk_pct": readiness.get("risk_pct") or levels.get("risk_pct"),
            }

        confidence = "high" if score >= SCORE_TIER_STRONG else "medium" if score >= SCORE_TIER_MEDIUM else "low"

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "direction": direction,
            "signal_type": "smc",
            "score": score,
            "legacy_score": legacy_score,
            "setup_score": readiness["setup_score"],
            "execution_score": readiness["execution_score"],
            "overall_score": readiness["overall_score"],
            "overall_formula": readiness["overall_formula"],
            "setup_stars": readiness["setup_stars"],
            "execution_stars": readiness["execution_stars"],
            "probability": readiness["probability"],
            "lifecycle_status": readiness["lifecycle_status"],
            "lifecycle_emoji": readiness["lifecycle_emoji"],
            "lifecycle_ru": readiness["lifecycle_ru"],
            "lifecycle_hint": readiness["lifecycle_hint"],
            "phase": readiness["phase"],
            "phase_ru": readiness["phase_ru"],
            "timing": readiness.get("timing"),
            "timing_emoji": readiness.get("timing_emoji"),
            "timing_ru": readiness.get("timing_ru"),
            "timing_reason": readiness.get("timing_reason"),
            "traffic_lights": readiness.get("traffic_lights"),
            "execution_breakdown": readiness.get("execution_breakdown"),
            "pd_zone": readiness.get("pd_zone"),
            "ideal_entry": readiness.get("ideal_entry"),
            "ideal_entry_low": readiness.get("ideal_entry_low"),
            "ideal_entry_high": readiness.get("ideal_entry_high"),
            "alternative_entry_low": readiness.get("alternative_entry_low"),
            "alternative_entry_high": readiness.get("alternative_entry_high"),
            "progress": readiness["progress"],
            "next_steps": readiness["next_steps"],
            "waiting_for": readiness["waiting_for"],
            "ai_comment": readiness["ai_conclusion"],
            "ai_conclusion": readiness["ai_conclusion"],
            "ai_verdict": readiness.get("ai_verdict"),
            "zone_note": readiness.get("zone_note"),
            "why_no_entry": readiness.get("why_no_entry"),
            "invalidation": readiness.get("invalidation") or [],
            "confidence_drivers": readiness.get("confidence_drivers") or [],
            "next_trigger": readiness.get("next_trigger"),
            "range_scale": readiness.get("range_scale"),
            "scenario_probability": readiness.get("scenario_probability"),
            "entry_probability_now": readiness.get("entry_probability_now"),
            "liquidity_quality": readiness.get("liquidity_quality"),
            "liquidity_stars": readiness.get("liquidity_stars"),
            "liquidity_hint": readiness.get("liquidity_hint"),
            "chasing_risk": readiness.get("chasing_risk"),
            "chasing_level": readiness.get("chasing_level"),
            "chasing_level_ru": readiness.get("chasing_level_ru"),
            "chasing_hint": readiness.get("chasing_hint"),
            "smart_money_activity": readiness.get("smart_money_activity"),
            "smart_money_ru": readiness.get("smart_money_ru"),
            "smart_money_score": readiness.get("smart_money_score"),
            "smart_money_stars": readiness.get("smart_money_stars"),
            "smart_money_hint": readiness.get("smart_money_hint"),
            "edge_score": readiness.get("edge_score"),
            "edge_stars": readiness.get("edge_stars"),
            "edge_reasons": readiness.get("edge_reasons") or [],
            "edge_hint": readiness.get("edge_hint"),
            "inefficiency_type": readiness.get("inefficiency_type"),
            "inefficiency_type_ru": readiness.get("inefficiency_type_ru"),
            "inefficiency_strength": readiness.get("inefficiency_strength"),
            "inefficiency_thesis": readiness.get("inefficiency_thesis"),
            "relative_volume": readiness.get("relative_volume"),
            "displacement_pct": readiness.get("displacement_pct"),
            "entry_blockers": readiness.get("entry_blockers") or [],
            "replay": readiness.get("replay") or [],
            "score_history": readiness.get("score_history") or [],
            "status_reason": readiness.get("status_reason"),
            "risk_label": readiness["risk_label"],
            "scenario_risk_pct": readiness["scenario_risk_pct"],
            "current_price": readiness["current_price"],
            "distance_pct": readiness["distance_pct"],
            "distance_label": readiness["distance_label"],
            "action": readiness["action"],
            "freshness": readiness["freshness"],
            "freshness_ru": readiness["freshness_ru"],
            "age_sec": readiness["age_sec"],
            "age_label": readiness["age_label"],
            "reeval_sec": readiness["reeval_sec"],
            "tier": tier,
            "confidence": confidence,
            "components": components,
            "reasons": {
                "found": reasons_found,
                "missing": reasons_missing,
                "checklist": checklist,
                "confirmed": readiness["confirmed"],
                "missing_items": readiness["missing_items"],
            },
            "levels": levels,
            "zones": zones,
            "market": {
                "ltf_trend": trend,
                "htf_trend": htf_trend,
                "funding": funding,
                "oi_change_pct": oi_change_pct,
                "rv": vol["rv"],
                "current_price": current_px,
            },
            "sequence_valid": sequence_valid,
            "readiness": readiness,
        }

    def classify(self, score: int) -> str:
        if score < SCORE_TIER_WEAK:
            return "weak"
        if score < SCORE_TIER_MEDIUM:
            return "medium"
        if score < SCORE_TIER_STRONG:
            return "strong"
        return "elite"

    def _weighted_total(self, components: dict[str, float]) -> int:
        total = 0.0
        weight_sum = 0.0
        for key, weight in self.weights.items():
            total += components.get(key, 0) * weight
            weight_sum += weight
        return int(round(total / weight_sum)) if weight_sum else 0

    def _infer_direction(
        self,
        sweeps: Sequence[EngineEvent],
        bos: Sequence[EngineEvent],
        choch: Sequence[EngineEvent],
        fvgs: Sequence[EngineEvent],
        pd: dict,
        trend: str,
        htf_trend: str,
    ) -> str:
        votes = {"LONG": 0, "SHORT": 0}
        # Sweep outweighs BOS — liquidity grab is the core thesis
        for e in sweeps:
            if e.direction == "bullish":
                votes["LONG"] += 2
            elif e.direction == "bearish":
                votes["SHORT"] += 2
        for e in list(fvgs):
            if e.direction == "bullish":
                votes["LONG"] += 1
            elif e.direction == "bearish":
                votes["SHORT"] += 1
        for e in list(bos) + list(choch):
            if e.direction == "bullish":
                votes["LONG"] += 0.5
            elif e.direction == "bearish":
                votes["SHORT"] += 0.5
        if pd.get("long_preferred"):
            votes["LONG"] += 1
        if pd.get("short_preferred"):
            votes["SHORT"] += 1
        if htf_trend == "bullish" or trend == "bullish":
            votes["LONG"] += 0.5
        if htf_trend == "bearish" or trend == "bearish":
            votes["SHORT"] += 0.5
        if votes["LONG"] == votes["SHORT"]:
            return "LONG" if trend != "bearish" else "SHORT"
        return "LONG" if votes["LONG"] > votes["SHORT"] else "SHORT"

    def _component_scores(self, **kwargs: Any) -> dict[str, float]:
        direction = kwargs["direction"]
        want = "bullish" if direction == "LONG" else "bearish"

        sweeps = kwargs["sweeps"]
        bos = kwargs["bos"]
        choch = kwargs["choch"]
        fvgs = kwargs["fvgs"]
        obs = kwargs["obs_bull"] if direction == "LONG" else kwargs["obs_bear"]
        vol = kwargs["vol"]
        oi_change_pct = kwargs["oi_change_pct"]
        trend = kwargs["trend"]
        htf_trend = kwargs["htf_trend"]
        pd = kwargs["pd"]

        def best(events: Sequence[EngineEvent], etype: Optional[str] = None) -> float:
            filtered = [
                e
                for e in events
                if e.direction == want and (etype is None or e.type == etype or etype in e.type)
            ]
            if not filtered:
                return 0.0
            return max(e.strength for e in filtered)

        liquidity = best(sweeps)
        bos_score = best(bos)
        if choch:
            bos_score = max(bos_score, best(choch) * 0.95)
        fvg_score = best(fvgs)
        ob_score = max((e.strength for e in obs), default=0.0)

        if direction == "LONG":
            htf = 90.0 if htf_trend == "bullish" else 55.0 if trend == "bullish" else 25.0
            if pd.get("zone") == "discount":
                htf = min(100.0, htf + 10)
        else:
            htf = 90.0 if htf_trend == "bearish" else 55.0 if trend == "bearish" else 25.0
            if pd.get("zone") == "premium":
                htf = min(100.0, htf + 10)

        volume_score = float(vol["score"])
        if direction == "LONG":
            oi_score = min(100.0, 40 + max(0.0, oi_change_pct) * 2)
        else:
            # Rising OI with shorts can still matter; treat absolute pressure lightly
            oi_score = min(100.0, 40 + abs(oi_change_pct))

        candles = kwargs.get("candles") or []
        impulse = self._impulse_metrics(candles, direction)
        # Delta proxy until real footprint: volume spike + OI pressure aligned with direction
        orderflow = min(
            100.0,
            volume_score * 0.45 + oi_score * 0.35 + impulse["impulse_speed"] * 0.20,
        )
        # Spread: unknown → neutral 55; caller may override via kwargs
        spread_score = float(kwargs.get("spread_score") if kwargs.get("spread_score") is not None else 55.0)
        book_score = float(kwargs.get("orderbook_score") if kwargs.get("orderbook_score") is not None else 30.0)

        return {
            "liquidity_sweep": liquidity,
            "bos": bos_score,
            "fvg": fvg_score,
            "order_block": ob_score,
            "htf_trend": htf,
            "volume": volume_score,
            "relative_volume": float(vol.get("rv") or 0),
            "rv": float(vol.get("rv") or 0),
            "oi": oi_score,
            "orderflow": orderflow,
            "spread": spread_score,
            "orderbook": book_score,
            "impulse_speed": impulse["impulse_speed"],
            "post_impulse": impulse["post_impulse"],
            "impulse_pct": impulse["impulse_pct"],
            "impulse_bars": impulse["impulse_bars"],
        }

    def _impulse_metrics(self, candles: Sequence[CandleBar], direction: str) -> dict[str, Any]:
        """Speed of move + what formed after the impulse (pullback / FVG / OB context)."""
        if len(candles) < 8:
            return {"impulse_speed": 0.0, "post_impulse": 0.0, "impulse_pct": 0.0, "impulse_bars": 0}
        # Look at last 1..6 bars for max directional move
        best_pct = 0.0
        best_n = 1
        close = float(candles[-1].close)
        for n in (1, 2, 3, 4, 5, 6):
            base = float(candles[-(n + 1)].close)
            if base <= 0:
                continue
            pct = (close - base) / base * 100
            signed = pct if direction == "LONG" else -pct
            if signed > best_pct:
                best_pct = signed
                best_n = n
        # Score: +8% in ≤3 bars ≈ strong; +18% in 9m (~1-2 bars on 15m) ≈ elite
        if best_pct >= 15:
            speed = 95.0
        elif best_pct >= 8:
            speed = 80.0
        elif best_pct >= 4:
            speed = 60.0
        elif best_pct >= 2:
            speed = 40.0
        else:
            speed = max(0.0, best_pct * 15)

        # Post-impulse: recent pullback after spike + volume cooling
        post = 35.0
        if len(candles) >= 4 and best_pct >= 3:
            last = candles[-1]
            prev = candles[-2]
            pullback = (
                (direction == "LONG" and float(last.low) < float(prev.low))
                or (direction == "SHORT" and float(last.high) > float(prev.high))
            )
            vol_cool = float(last.volume) < float(prev.volume) * 0.9 if prev.volume else False
            if pullback:
                post += 25
            if vol_cool:
                post += 15
            # Wick rejection after impulse
            if direction == "LONG" and float(last.close) > float(last.open):
                post += 10
            if direction == "SHORT" and float(last.close) < float(last.open):
                post += 10
        return {
            "impulse_speed": min(100.0, speed),
            "post_impulse": min(100.0, post),
            "impulse_pct": round(best_pct, 2),
            "impulse_bars": best_n,
        }

    def _sequence_valid(self, components: dict[str, float], direction: str) -> bool:
        # Prefer Sweep + imbalance; allow FVG+OB forming without Sweep yet
        sweep_ok = components.get("liquidity_sweep", 0) >= 50
        imbalance_ok = components.get("fvg", 0) >= 40 or components.get("order_block", 0) >= 40
        flow_ok = (
            components.get("oi", 0) >= 45
            or components.get("orderflow", 0) >= 45
            or components.get("volume", 0) >= 50
        )
        return bool((sweep_ok and imbalance_ok) or (imbalance_ok and flow_ok))

    def _reasons(
        self,
        components: dict[str, float],
        direction: str,
        vol: dict,
        pd: dict,
        htf_trend: str,
    ) -> tuple[list[str], list[str]]:
        found: list[str] = []
        missing: list[str] = []
        labels = {
            "liquidity_sweep": "Liquidity Sweep",
            "fvg": "FVG / Imbalance",
            "order_block": "Order Block",
            "oi": "Open Interest",
            "orderflow": "Order Flow / Delta",
            "volume": "Volume Spike",
            "impulse_speed": "Impulse Speed",
            "post_impulse": "Post-Impulse Structure",
            "bos": "BOS (confirm)",
            "htf_trend": "HTF Trend",
        }
        for key, label in labels.items():
            if components.get(key, 0) >= 50:
                if key == "volume":
                    found.append(f"{label} (RV x{vol['rv']})")
                elif key == "impulse_speed" and components.get("impulse_pct"):
                    found.append(f"{label} +{components['impulse_pct']}% / {int(components.get('impulse_bars') or 1)} bars")
                else:
                    found.append(label)
            elif key in ("liquidity_sweep", "fvg", "order_block", "oi", "orderflow", "volume"):
                missing.append(f"No {label.lower()}")

        if direction == "LONG" and pd.get("zone") == "premium":
            missing.append("Price in premium (less ideal for LONG)")
        if direction == "SHORT" and pd.get("zone") == "discount":
            missing.append("Price in discount (less ideal for SHORT)")
        return found, missing

    def _trade_levels(
        self,
        candles: Sequence[CandleBar],
        direction: str,
        sweeps: Sequence[EngineEvent],
        fvgs: Sequence[EngineEvent],
        obs_bull: Sequence[EngineEvent],
        obs_bear: Sequence[EngineEvent],
    ) -> dict[str, Any]:
        price = candles[-1].close
        atr_val = atr(candles) or price * 0.01

        if direction == "LONG":
            zone = next((e for e in obs_bull), None) or next(
                (e for e in fvgs if e.direction == "bullish"), None
            )
            entry = price
            stop = (zone.bottom if zone and zone.bottom else price - atr_val * 1.2)
            if sweeps and sweeps[-1].direction == "bullish" and sweeps[-1].price:
                stop = min(stop, sweeps[-1].price * 0.998)
            risk = max(entry - stop, atr_val * 0.3)
            tp1 = entry + risk * 2
            tp2 = entry + risk * 3
            tp3 = entry + risk * 4.3
        else:
            zone = next((e for e in obs_bear), None) or next(
                (e for e in fvgs if e.direction == "bearish"), None
            )
            entry = price
            stop = (zone.top if zone and zone.top else price + atr_val * 1.2)
            if sweeps and sweeps[-1].direction == "bearish" and sweeps[-1].price:
                stop = max(stop, sweeps[-1].price * 1.002)
            # SHORT stop must always be above entry
            stop = max(float(stop), entry + atr_val * 0.35, entry * 1.006)
            risk = max(stop - entry, atr_val * 0.3)
            tp1 = entry - risk * 2
            tp2 = entry - risk * 3
            tp3 = entry - risk * 4.3

        if direction == "LONG":
            # LONG stop must always be below entry
            stop = min(float(stop), entry - atr_val * 0.35, entry * 0.994)
            risk = max(entry - stop, atr_val * 0.3)
            tp1 = entry + risk * 2
            tp2 = entry + risk * 3
            tp3 = entry + risk * 4.3

        rr = round((abs(tp2 - entry) / risk), 2) if risk else None
        risk_pct = round(risk / entry * 100, 2) if entry else None
        return {
            "entry": round(entry, 8),
            "stop": round(stop, 8),
            "tp1": round(tp1, 8),
            "tp2": round(tp2, 8),
            "tp3": round(tp3, 8),
            "risk_reward": rr,
            "risk_pct": risk_pct,
        }

    def _empty(self, symbol: str, timeframe: str, reason: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "direction": "LONG",
            "signal_type": "smc",
            "score": 0,
            "setup_score": 0,
            "execution_score": 0,
            "probability": 0,
            "lifecycle_status": "IGNORE",
            "lifecycle_emoji": "⚪",
            "lifecycle_ru": "Игнорировать",
            "lifecycle_hint": "Слабый сценарий",
            "phase": "unknown",
            "phase_ru": "Неизвестно",
            "progress": [],
            "next_steps": [],
            "ai_comment": reason,
            "risk_label": "Высокий",
            "tier": "weak",
            "confidence": "low",
            "components": {},
            "reasons": {"found": [], "missing": [reason], "checklist": {}},
            "levels": {},
            "zones": {},
            "market": {},
            "sequence_valid": False,
        }
