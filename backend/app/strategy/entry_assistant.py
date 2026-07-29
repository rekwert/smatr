"""AI Entry Assistant — trade lifecycle statuses (WATCH → ENTRY READY → …).

Не «покупай сейчас», а фаза + зона + триггеры + статус.
"""

from __future__ import annotations

from typing import Any, Literal, Optional, Sequence

from app.engines.regime.analyzer import MarketRegimeDetector
from app.engines.scoring.calculator import ScoreCalculator
from app.engines.volume.analyzer import VolumeAnalyzer
from app.market_data.candles import CandleBar
from app.strategy.engine import StrategyEngine

EntryStatus = Literal[
    "WATCH",
    "SETUP_FORMING",
    "APPROACHING_ENTRY",
    "ENTRY_READY",
    "MISSED",
    "INVALIDATED",
]

EntryMode = Literal["conservative", "balanced", "aggressive"]

STATUS_RU = {
    "IGNORE": "Игнорировать",
    "WATCH": "НАБЛЮДЕНИЕ",
    "SETUP_FORMING": "СЕТАП ФОРМИРУЕТСЯ",
    "APPROACHING_ENTRY": "ПРИБЛИЖЕНИЕ К ЗОНЕ",
    "ENTRY_READY": "ГОТОВ К ВХОДУ",
    "MISSED": "ОПОЗДАЛИ",
    "INVALIDATED": "СЦЕНАРИЙ СЛОМАН",
}

PHASE_RU = {
    "accumulation": "Накопление",
    "expansion": "Расширение",
    "trending": "Тренд",
    "ranging": "Флэт",
    "unknown": "Неизвестно",
}


# Triggers required per mode (all must be True for ENTRY_READY)
MODE_TRIGGERS: dict[EntryMode, list[str]] = {
    "conservative": ["liquidity_sweep", "choch", "volume"],
    "balanced": ["liquidity_sweep", "bos", "fvg", "oi"],
    "aggressive": ["compression_or_anomaly", "ai_high"],
}


class EntryAssistant:
    def __init__(self) -> None:
        self.scorer = ScoreCalculator()
        self.strategy = StrategyEngine()
        self.regime = MarketRegimeDetector()
        self.volume = VolumeAnalyzer()

    def evaluate(
        self,
        symbol: str,
        candles: Sequence[CandleBar],
        *,
        exchange: str = "bybit",
        mode: EntryMode = "balanced",
        oi_change_pct: float = 0.0,
        pump_score: float = 0.0,
        ai_score: float = 0.0,
        hunter: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if len(candles) < 40:
            return self._empty(symbol, exchange, "Мало истории для оценки входа")

        smc = self.scorer.analyze_symbol(
            symbol, candles, oi_change_pct=oi_change_pct
        )
        risk_map = {"conservative": "conservative", "balanced": "normal", "aggressive": "aggressive"}
        plan = self.strategy.build_plan(
            symbol,
            candles,
            smc=smc,
            hunter=hunter,
            exchange=exchange,
            risk_profile=risk_map[mode],  # type: ignore[arg-type]
        )
        regime = self.regime.analyze(candles)
        vol = self.volume.analyze(candles)
        checklist = (smc.get("reasons") or {}).get("checklist") or {}
        zones = smc.get("zones") or {}

        direction = str(plan.get("direction") or "LONG").upper()
        entry_zone = plan.get("entry_zone") or {}
        if isinstance(entry_zone, (list, tuple)) and len(entry_zone) >= 2:
            low = float(entry_zone[0])
            high = float(entry_zone[1])
        else:
            low = float(
                (entry_zone.get("low") if isinstance(entry_zone, dict) else None)
                or plan.get("entry")
                or candles[-1].close
            )
            high = float(
                (entry_zone.get("high") if isinstance(entry_zone, dict) else None)
                or plan.get("entry")
                or candles[-1].close
            )
        if low > high:
            low, high = high, low
        mid = (low + high) / 2
        current = float(candles[-1].close)
        stop = float(plan.get("stop_loss") or 0)

        # Distance to zone (%). Positive = price above zone for LONG (need pullback)
        if direction == "LONG":
            if current < low:
                distance_pct = (current - low) / mid * 100  # below zone
            elif current > high:
                distance_pct = (current - high) / mid * 100  # above zone
            else:
                distance_pct = 0.0
            in_zone = low <= current <= high
            past_zone = current > high * 1.015  # >1.5% above zone high
            invalidated = stop > 0 and current < stop
            # Missed: already expanded far above entry
            missed = current >= mid * 1.12 or (
                past_zone and abs(distance_pct) >= 8
            )
        else:
            if current > high:
                distance_pct = (current - high) / mid * 100
            elif current < low:
                distance_pct = (current - low) / mid * 100
            else:
                distance_pct = 0.0
            in_zone = low <= current <= high
            past_zone = current < low * 0.985
            invalidated = stop > 0 and current > stop
            missed = current <= mid * 0.88 or (past_zone and abs(distance_pct) >= 8)

        triggers = self._build_triggers(
            checklist=checklist,
            zones=zones,
            vol=vol,
            oi_change_pct=oi_change_pct,
            pump_score=pump_score,
            ai_score=ai_score or float(smc.get("score") or 0),
            regime=regime,
            mode=mode,
        )
        mode_ok = self._mode_satisfied(triggers, mode)

        phase = str(regime.get("market_regime") or "unknown")
        stage = self._stage_text(phase, triggers, in_zone, mode)

        status = self._resolve_status(
            invalidated=invalidated,
            missed=missed,
            in_zone=in_zone,
            mode_ok=mode_ok,
            triggers=triggers,
            distance_pct=distance_pct,
            direction=direction,
            score=float(smc.get("score") or 0),
            phase=phase,
        )

        liq_map = self._liquidity_map(zones, current, direction, plan)

        action_ru = {
            "WATCH": "Ждать. Монета интересна, подтверждения нет.",
            "SETUP_FORMING": "Сетап собирается. Следить за sweep / структурой.",
            "APPROACHING_ENTRY": "Ждём откат/подход к зоне входа.",
            "ENTRY_READY": "Цена в зоне + триггеры режима. Можно рассматривать вход вручную.",
            "MISSED": "Цена ушла от зоны. Не догонять.",
            "INVALIDATED": "Стоп/структура сломаны. Сценарий отменён.",
        }[status]

        return {
            "symbol": symbol.upper(),
            "exchange": exchange,
            "mode": mode,
            "status": status,
            "status_ru": STATUS_RU[status],
            "phase": phase,
            "phase_ru": PHASE_RU.get(phase, phase),
            "phase_confidence": regime.get("confidence"),
            "current_stage": stage,
            "direction": direction,
            "current_price": current,
            "entry_zone": {"low": round(low, 8), "high": round(high, 8)},
            "entry": plan.get("entry"),
            "stop": stop,
            "targets": plan.get("targets"),
            "risk_reward": plan.get("risk_reward"),
            "distance_pct": round(distance_pct, 2),
            "in_zone": in_zone,
            "triggers": triggers,
            "triggers_needed": MODE_TRIGGERS[mode],
            "mode_satisfied": mode_ok,
            "liquidity_map": liq_map,
            "probability": self._probability(status, smc, regime, triggers, mode_ok),
            "score": smc.get("score"),
            "action": action_ru,
            "checklist_smc": checklist,
            "disclaimer": "Аналитический статус. Не торговый приказ. Вход только вручную.",
        }

    def _build_triggers(
        self,
        *,
        checklist: dict,
        zones: dict,
        vol: dict,
        oi_change_pct: float,
        pump_score: float,
        ai_score: float,
        regime: dict,
        mode: EntryMode,
    ) -> dict[str, Any]:
        sweeps = zones.get("liquidity_sweeps") or []
        choch = zones.get("choch") or []
        bos = zones.get("bos") or []
        fvg = zones.get("fvg") or []
        rv = float(vol.get("relative_volume") or 0)

        liquidity_sweep = bool(checklist.get("liquidity_sweep")) or bool(sweeps)
        choch_ok = bool(choch) or (
            # approximate: bos after sweep often implies shift
            liquidity_sweep and bool(bos)
        )
        # Prefer explicit choch list
        if zones.get("choch") is not None:
            choch_ok = len(choch) > 0

        volume_ok = rv >= 1.5 or bool(checklist.get("volume"))
        bos_ok = bool(checklist.get("bos")) or bool(bos)
        fvg_ok = bool(checklist.get("fvg")) or bool(fvg)
        oi_ok = abs(oi_change_pct) >= 8 or bool(checklist.get("oi"))
        compression = str(regime.get("market_regime")) == "accumulation"
        anomaly = rv >= 3 or pump_score >= 85
        compression_or_anomaly = compression or anomaly
        ai_high = ai_score >= 90 or pump_score >= 90

        return {
            "liquidity_sweep": {
                "ok": liquidity_sweep,
                "label": "Liquidity Sweep",
                "label_ru": "Снятие ликвидности",
            },
            "choch": {
                "ok": choch_ok,
                "label": "CHoCH",
                "label_ru": "Смена характера (CHoCH)",
            },
            "bos": {
                "ok": bos_ok,
                "label": "BOS",
                "label_ru": "Пробой структуры (BOS)",
            },
            "fvg": {
                "ok": fvg_ok,
                "label": "FVG",
                "label_ru": "Имбаланс (FVG)",
            },
            "volume": {
                "ok": volume_ok,
                "label": "Volume",
                "label_ru": f"Объём (RV {rv:.1f}x)",
            },
            "oi": {
                "ok": oi_ok,
                "label": "OI",
                "label_ru": f"OI ({oi_change_pct:+.1f}%)",
            },
            "compression_or_anomaly": {
                "ok": compression_or_anomaly,
                "label": "Compression/Anomaly",
                "label_ru": "Сжатие / аномалия объёма",
            },
            "ai_high": {
                "ok": ai_high,
                "label": "AI>90",
                "label_ru": f"AI/Pump score ≥90 (сейчас {max(ai_score, pump_score):.0f})",
            },
        }

    def _mode_satisfied(self, triggers: dict, mode: EntryMode) -> bool:
        keys = MODE_TRIGGERS[mode]
        return all(triggers.get(k, {}).get("ok") for k in keys)

    def _resolve_status(
        self,
        *,
        invalidated: bool,
        missed: bool,
        in_zone: bool,
        mode_ok: bool,
        triggers: dict,
        distance_pct: float,
        direction: str,
        score: float,
        phase: str,
    ) -> EntryStatus:
        if invalidated:
            return "INVALIDATED"
        if missed and not in_zone:
            return "MISSED"
        if in_zone and mode_ok:
            return "ENTRY_READY"
        if in_zone and not mode_ok:
            return "SETUP_FORMING"
        # Approaching: within ~3% of zone for LONG above zone (waiting pullback)
        if direction == "LONG" and 0 < distance_pct <= 3.5:
            return "APPROACHING_ENTRY"
        if direction == "SHORT" and -3.5 <= distance_pct < 0:
            return "APPROACHING_ENTRY"
        if any(triggers[k]["ok"] for k in ("liquidity_sweep", "bos", "choch", "fvg")):
            return "SETUP_FORMING"
        if score >= 70 or phase == "accumulation":
            return "WATCH"
        return "WATCH"

    def _stage_text(
        self, phase: str, triggers: dict, in_zone: bool, mode: EntryMode
    ) -> str:
        if phase == "accumulation" and not triggers["liquidity_sweep"]["ok"]:
            return "Ждём снятие ликвидности (sweep) перед импульсом"
        missing = [
            triggers[k]["label_ru"]
            for k in MODE_TRIGGERS[mode]
            if not triggers.get(k, {}).get("ok")
        ]
        if in_zone and missing:
            return "Цена в зоне — не хватает: " + ", ".join(missing)
        if missing:
            return "Нужно: " + ", ".join(missing[:3])
        return "Триггеры режима выполнены"

    def _liquidity_map(
        self, zones: dict, current: float, direction: str, plan: dict
    ) -> dict[str, Any]:
        sweeps = zones.get("liquidity_sweeps") or []
        eq_h = zones.get("equal_highs") or []
        eq_l = zones.get("equal_lows") or []
        fvg = zones.get("fvg") or []
        targets = plan.get("targets") or {}

        pool_below = None
        pool_above = None
        if eq_l:
            pool_below = min(
                (float(x.get("price") or current) for x in eq_l),
                default=None,
            )
        if eq_h:
            pool_above = max(
                (float(x.get("price") or current) for x in eq_h),
                default=None,
            )
        if sweeps:
            last = sweeps[-1]
            p = float(last.get("price") or 0)
            if last.get("direction") == "bullish":
                pool_below = p
            else:
                pool_above = p

        nearest_fvg = None
        if fvg:
            nearest_fvg = fvg[0]

        return {
            "current": current,
            "liquidity_below": pool_below,
            "liquidity_above": pool_above,
            "nearest_fvg": nearest_fvg,
            "tp1": targets.get("tp1"),
            "tp2": targets.get("tp2"),
            "note_ru": (
                "Часто перед ростом снимают стопы снизу"
                if direction == "LONG"
                else "Часто перед падением снимают стопы сверху"
            ),
        }

    def _probability(
        self,
        status: EntryStatus,
        smc: dict,
        regime: dict,
        triggers: dict,
        mode_ok: bool,
    ) -> int:
        base = int(smc.get("score") or 50)
        if regime.get("market_regime") == "accumulation":
            base += 5
        ok_n = sum(1 for t in triggers.values() if t.get("ok"))
        base += ok_n * 3
        if status == "ENTRY_READY":
            base += 8
        if status == "MISSED":
            base = min(base, 35)
        if status == "INVALIDATED":
            base = min(base, 20)
        if mode_ok:
            base += 5
        return int(max(5, min(95, base)))

    def _empty(self, symbol: str, exchange: str, msg: str) -> dict[str, Any]:
        return {
            "symbol": symbol.upper(),
            "exchange": exchange,
            "status": "WATCH",
            "status_ru": STATUS_RU["WATCH"],
            "action": msg,
            "triggers": {},
            "disclaimer": "Аналитический статус. Не торговый приказ.",
        }
