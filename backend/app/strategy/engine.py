"""Trading Strategy Engine + Risk Management (Part 11)."""

from __future__ import annotations

from typing import Any, Literal, Optional, Sequence

from app.engines.scoring.calculator import ScoreCalculator
from app.market_data.candles import CandleBar, atr

SetupType = Literal["smc_reversal", "trend_continuation", "early_pump", "breakout_retest", "unknown"]
RiskProfile = Literal["conservative", "normal", "aggressive"]

RISK_PCT = {"conservative": 0.5, "normal": 1.0, "aggressive": 2.0}
MAX_LEVERAGE = {"btc": 5, "alt": 3, "low_liq": 2}


class StrategyEngine:
    def __init__(self) -> None:
        self.scorer = ScoreCalculator()

    def build_plan(
        self,
        symbol: str,
        candles: Sequence[CandleBar],
        *,
        direction: Optional[str] = None,
        smc: Optional[dict[str, Any]] = None,
        pump: Optional[dict[str, Any]] = None,
        hunter: Optional[dict[str, Any]] = None,
        account_balance: float = 10_000.0,
        risk_profile: RiskProfile = "normal",
        spread_pct: Optional[float] = None,
        orderbook_depth: float = 0.0,
        exchange: str = "bybit",
    ) -> dict[str, Any]:
        smc = smc or self.scorer.analyze_symbol(symbol, candles)
        direction = (direction or smc.get("direction") or "LONG").upper()
        setup = self.classify_setup(smc, pump, hunter)
        levels = smc.get("levels") or {}
        zones = smc.get("zones") or {}

        entry = self._entry_model(candles, direction, levels, zones, smc, hunter)
        stop = self._stop_model(candles, direction, entry["entry"], levels, zones)
        targets = self._targets(candles, direction, entry["entry"], stop["stop"], zones)
        risk = abs(entry["entry"] - stop["stop"])
        reward = abs(targets["tp2"] - entry["entry"])
        rr = round(reward / risk, 2) if risk else 0.0

        risk_pct = RISK_PCT[risk_profile]
        position = self.position_size(account_balance, risk_pct, entry["entry"], stop["stop"])
        leverage = self.leverage_cap(symbol, hunter, position["notional"], account_balance)
        liq_risk = self.liquidity_risk(
            position["notional"], orderbook_depth, spread_pct
        )
        confidence = self.confidence_score(smc, hunter, rr, liq_risk)

        invalidation = [
            f"Acceptance beyond stop {stop['stop']}",
            "CHoCH against position",
            "Volume disappearance / liquidity break",
        ]

        return {
            "symbol": symbol.upper(),
            "exchange": exchange,
            "direction": direction,
            "setup": setup,
            "setup_label": self._setup_label(setup),
            "entry_zone": entry["zone"],
            "entry": entry["entry"],
            "entry_model": entry["model"],
            "entry_score": entry["score"],
            "stop_loss": stop["stop"],
            "stop_type": stop["type"],
            "targets": {
                "tp1": targets["tp1"],
                "tp2": targets["tp2"],
                "tp3": targets["tp3"],
                "distribution": {"tp1": 0.3, "tp2": 0.4, "tp3": 0.3},
            },
            "risk_reward": rr,
            "risk_pct": risk_pct,
            "position": position,
            "leverage_max": leverage,
            "liquidity_risk": liq_risk,
            "confidence": confidence,
            "invalidation": invalidation,
            "reasons": (smc.get("reasons") or {}).get("found") or (hunter or {}).get("reasons") or [],
            "mode_recommendation": "confirmation" if confidence >= 85 else "analysis",
            "status": "WATCHING",
            "disclaimer": "Trade plan is analytical. Not an order. No guaranteed outcome.",
        }

    def classify_setup(
        self,
        smc: dict[str, Any],
        pump: Optional[dict[str, Any]],
        hunter: Optional[dict[str, Any]],
    ) -> SetupType:
        cl = (smc.get("reasons") or {}).get("checklist") or {}
        if hunter and hunter.get("score", 0) >= 85:
            return "early_pump"
        if cl.get("liquidity_sweep") and cl.get("fvg"):
            return "smc_reversal"
        if cl.get("bos") and cl.get("fvg"):
            return "trend_continuation"
        if pump and pump.get("total", 0) >= 80 and (pump.get("components") or {}).get("breakout", 0) >= 70:
            return "breakout_retest"
        return "unknown"

    def position_size(
        self,
        balance: float,
        risk_pct: float,
        entry: float,
        stop: float,
    ) -> dict[str, float]:
        risk_usd = balance * (risk_pct / 100)
        stop_dist = abs(entry - stop) / (entry or 1e-9)
        notional = risk_usd / stop_dist if stop_dist else 0.0
        qty = notional / entry if entry else 0.0
        return {
            "risk_usd": round(risk_usd, 2),
            "notional": round(notional, 2),
            "qty": round(qty, 8),
            "stop_distance_pct": round(stop_dist * 100, 3),
        }

    def leverage_cap(
        self,
        symbol: str,
        hunter: Optional[dict[str, Any]],
        notional: float,
        balance: float,
    ) -> int:
        base = symbol.upper().replace("USDT", "")
        if base in ("BTC", "ETH"):
            cap = MAX_LEVERAGE["btc"]
        elif hunter and hunter.get("cap_class") in ("micro", "small"):
            cap = MAX_LEVERAGE["low_liq"]
        else:
            cap = MAX_LEVERAGE["alt"]
        needed = int(max(1, round(notional / max(balance, 1))))
        return min(cap, max(1, needed))

    def liquidity_risk(
        self,
        notional: float,
        depth: float,
        spread_pct: Optional[float],
    ) -> dict[str, Any]:
        flags = []
        level = "low"
        if spread_pct is not None:
            if spread_pct >= 2:
                flags.append("Spread dangerous")
                level = "high"
            elif spread_pct >= 0.5:
                flags.append("Elevated spread")
                level = "medium"
        if depth > 0 and notional > depth:
            flags.append("Position > orderbook depth")
            level = "high"
        elif depth > 0 and notional > depth * 0.5:
            flags.append("Position large vs depth")
            if level == "low":
                level = "medium"
        slippage_est = min(5.0, (notional / depth) * 0.5) if depth else None
        if slippage_est and slippage_est > 0.5:
            flags.append("Expected slippage > 0.5%")
            level = "high"
        return {
            "level": level,
            "flags": flags,
            "expected_slippage_pct": round(slippage_est, 3) if slippage_est is not None else None,
            "approve": level != "high",
        }

    def confidence_score(
        self,
        smc: dict[str, Any],
        hunter: Optional[dict[str, Any]],
        rr: float,
        liq_risk: dict[str, Any],
    ) -> int:
        setup_q = float(smc.get("score") or 0)
        ctx = 70.0
        if hunter:
            ctx = float(hunter.get("quality") or hunter.get("score") or 60)
        liq = {"low": 90, "medium": 70, "high": 40}.get(liq_risk.get("level"), 60)
        vol = float((smc.get("components") or {}).get("volume") or 50)
        rr_score = min(100.0, rr / 4 * 100)
        conf = setup_q * 0.3 + ctx * 0.2 + liq * 0.15 + vol * 0.15 + rr_score * 0.2
        return int(max(0, min(100, round(conf))))

    def _entry_model(self, candles, direction, levels, zones, smc, hunter) -> dict:
        price = candles[-1].close
        score = int(smc.get("score") or 0)
        fvgs = [z for z in (zones.get("fvg") or []) if z.get("direction") == ("bullish" if direction == "LONG" else "bearish")]
        obs = [
            z
            for z in (zones.get("order_blocks") or [])
            if z.get("direction") == ("bullish" if direction == "LONG" else "bearish")
        ]
        zone_obj = (obs[0] if obs else None) or (fvgs[0] if fvgs else None)

        if score >= 95 and hunter and hunter.get("score", 0) >= 95:
            return {
                "model": "market",
                "entry": price,
                "zone": [round(price * 0.998, 8), round(price * 1.002, 8)],
                "score": 70,
            }

        if zone_obj and zone_obj.get("bottom") is not None and zone_obj.get("top") is not None:
            mid = (float(zone_obj["top"]) + float(zone_obj["bottom"])) / 2
            return {
                "model": "limit",
                "entry": mid,
                "zone": [float(zone_obj["bottom"]), float(zone_obj["top"])],
                "score": int(zone_obj.get("strength") or 80),
            }

        # scaling default around structure entry
        base = float(levels.get("entry") or price)
        return {
            "model": "scaling",
            "entry": base,
            "zone": [round(base * 0.99, 8), round(base * 1.01, 8)],
            "score": 65,
            "legs": [
                {"pct": 0.3, "price": round(base * 1.004, 8)},
                {"pct": 0.4, "price": base},
                {"pct": 0.3, "price": round(base * 0.996, 8)},
            ],
        }

    def _stop_model(self, candles, direction, entry, levels, zones) -> dict:
        atr_val = atr(candles) or entry * 0.01
        structural = levels.get("stop")
        if structural:
            dist = abs(entry - float(structural))
            if dist < atr_val * 0.5:
                # too tight → ATR stop
                stop = entry - atr_val * 1.5 if direction == "LONG" else entry + atr_val * 1.5
                return {"stop": round(stop, 8), "type": "atr"}
            if dist > atr_val * 4:
                stop = entry - atr_val * 2 if direction == "LONG" else entry + atr_val * 2
                return {"stop": round(stop, 8), "type": "atr_capped"}
            return {"stop": round(float(structural), 8), "type": "structural"}
        stop = entry - atr_val * 1.5 if direction == "LONG" else entry + atr_val * 1.5
        return {"stop": round(stop, 8), "type": "atr"}

    def _targets(self, candles, direction, entry, stop, zones) -> dict:
        risk = abs(entry - stop) or 1e-9
        if direction == "LONG":
            # liquidity highs as soft targets
            eqh = zones.get("equal_highs") or []
            liq = float(eqh[0]["price"]) if eqh and eqh[0].get("price") else None
            tp1 = entry + risk * 2
            tp2 = entry + risk * 3.5
            tp3 = liq if liq and liq > tp2 else entry + risk * 5
        else:
            eql = zones.get("equal_lows") or []
            liq = float(eql[0]["price"]) if eql and eql[0].get("price") else None
            tp1 = entry - risk * 2
            tp2 = entry - risk * 3.5
            tp3 = liq if liq and liq < tp2 else entry - risk * 5
        return {"tp1": round(tp1, 8), "tp2": round(tp2, 8), "tp3": round(tp3, 8)}

    @staticmethod
    def _setup_label(setup: SetupType) -> str:
        return {
            "smc_reversal": "Type A · SMC Reversal",
            "trend_continuation": "Type B · Trend Continuation",
            "early_pump": "Type C · Early Pump",
            "breakout_retest": "Type D · Breakout Retest",
            "unknown": "Unclassified Setup",
        }[setup]
