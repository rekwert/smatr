"""Low Liquidity Coin Hunter — Part 10.

Finds pre-expansion states: accumulation → compression → volume → structure → move.
NOT chasing already-pumped coins.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from app.engines.liquidity.analyzer import LiquidityAnalyzer
from app.engines.pump_detector.analyzer import PumpDetector
from app.engines.scoring.calculator import ScoreCalculator
from app.engines.structure.analyzer import StructureAnalyzer
from app.engines.volume.analyzer import VolumeAnalyzer
from app.exchange_layer.scanners import liquidity_score
from app.market_data.candles import CandleBar, atr


EXCHANGE_QUALITY = {
    "bybit": 100,
    "okx": 95,
    "bitget": 85,
    "bingx": 75,
    "mexc": 70,
    "kucoin": 70,
}


def classify_cap(volume_24h: float) -> str:
    # Volume used as liquidity proxy when mcap unavailable
    if volume_24h < 10_000_000:
        return "micro"
    if volume_24h < 50_000_000:
        return "small"
    if volume_24h < 200_000_000:
        return "mid"
    return "large"


def hunter_status(score: int) -> str:
    if score >= 95:
        return "ACTIVE"
    if score >= 85:
        return "READY"
    if score >= 70:
        return "PREPARING"
    if score >= 50:
        return "SLEEPING"
    return "IGNORE"


class LowLiquidityHunter:
    """Part 10 engine — analyzes one symbol's candles + market meta."""

    def __init__(self) -> None:
        self.volume = VolumeAnalyzer()
        self.structure = StructureAnalyzer()
        self.liquidity = LiquidityAnalyzer()
        self.scorer = ScoreCalculator()
        self.pump = PumpDetector()

    def analyze(
        self,
        symbol: str,
        candles: Sequence[CandleBar],
        *,
        exchange: str = "bybit",
        volume_24h: float = 0.0,
        spread_pct: Optional[float] = None,
        oi_change_pct: float = 0.0,
        orderbook_depth: float = 0.0,
        trades_count: int = 0,
        is_new_listing: bool = False,
        whale_buys: Optional[list[dict[str, Any]]] = None,
        buy_pressure: Optional[float] = None,
    ) -> dict[str, Any]:
        if len(candles) < 40:
            return {
                "symbol": symbol,
                "exchange": exchange,
                "score": 0,
                "status": "IGNORE",
                "reasons": ["Insufficient history"],
                "components": {},
            }

        # Primary filters (Part 10 §5)
        if volume_24h and volume_24h < 500_000:
            return self._reject(symbol, exchange, "Volume 24h < 500k")
        if spread_pct is not None and spread_pct > 1.0:
            return self._reject(symbol, exchange, f"Spread {spread_pct:.2f}% > 1%")

        cap = classify_cap(volume_24h or 0)
        # Focus 5M–100M band preferred but allow micro with strong signals
        liq = liquidity_score(
            volume_24h or 0,
            depth_usd=orderbook_depth,
            spread_pct=spread_pct,
            trades_count=trades_count,
        )
        # Blend exchange quality into liquidity score (10% weight in TZ)
        eq = EXCHANGE_QUALITY.get(exchange.lower(), 60)
        liq = round(liq * 0.9 + eq * 0.1, 1)

        accumulation = self._accumulation(candles)
        atr_comp = self._atr_compression(candles)
        range_comp = self._range_compression(candles)
        vol = self.volume.analyze(candles)
        volume_growth = self._volume_growth(candles)
        structure = self._structure_prep(candles)
        whale = self._whale_score(whale_buys, candles)
        pressure = buy_pressure if buy_pressure is not None else self._estimate_buy_pressure(candles)
        oi_score = min(100.0, 40 + max(0.0, oi_change_pct) * 2)
        listing_bonus = 90.0 if is_new_listing else 20.0

        # Pump Score weights (Part 10 §17)
        components = {
            "accumulation": round((accumulation + atr_comp + range_comp) / 3, 1),
            "volume_growth": round((volume_growth + float(vol["score"])) / 2, 1),
            "liquidity_change": round(100 - min(liq, 100) * 0.5 + (20 if vol["spike"] else 0), 1),
            "whale_activity": whale,
            "structure": structure,
            "oi_growth": oi_score,
            "new_listing": listing_bonus,
            "buy_pressure": round(pressure * 100, 1) if pressure <= 1 else round(pressure, 1),
            "liquidity_score": liq,
            "atr_compression": atr_comp,
            "range_compression": range_comp,
        }
        # Cap liquidity_change
        components["liquidity_change"] = min(100.0, max(0.0, components["liquidity_change"]))

        weights = {
            "accumulation": 20,
            "volume_growth": 20,
            "liquidity_change": 15,
            "whale_activity": 15,
            "structure": 15,
            "oi_growth": 10,
            "new_listing": 5,
        }
        total = sum(components[k] * w for k, w in weights.items())
        score = int(round(total / sum(weights.values())))

        false_flags = self._false_pump_flags(candles, vol, spread_pct)
        quality = self._quality_score(score, false_flags, liq, spread_pct)

        # Penalize already exploded moves (philosophy: not chase +100%)
        recent_move = self._recent_move_pct(candles, lookback=24)
        if recent_move >= 40:
            score = max(0, score - 35)
            false_flags.append("Already extended (>40% recent)")
        elif recent_move >= 25:
            score = max(0, score - 15)
            false_flags.append("Partially extended")

        status = hunter_status(score)
        reasons = []
        if components["accumulation"] >= 70:
            reasons.append("Compression / Accumulation")
        if components["volume_growth"] >= 70:
            reasons.append(f"Volume Growth (RV x{vol['rv']})")
        if oi_change_pct >= 15:
            reasons.append(f"OI {oi_change_pct:+.1f}%")
        if whale >= 70:
            reasons.append("Whale Activity")
        if structure >= 70:
            reasons.append("Structure preparing / sweep")
        if is_new_listing:
            reasons.append("New Listing")
        if pressure and (pressure if pressure > 1 else pressure * 100) >= 60:
            reasons.append("Buy Pressure")

        return {
            "symbol": symbol.upper(),
            "exchange": exchange.lower(),
            "score": score,
            "quality": quality,
            "status": status,
            "cap_class": cap,
            "reasons": reasons,
            "red_flags": false_flags,
            "components": components,
            "market": {
                "volume_24h": volume_24h,
                "spread_pct": spread_pct,
                "oi_change_pct": oi_change_pct,
                "recent_move_pct": round(recent_move, 2),
                "rv": vol["rv"],
            },
        }

    def _reject(self, symbol: str, exchange: str, reason: str) -> dict[str, Any]:
        return {
            "symbol": symbol.upper(),
            "exchange": exchange.lower(),
            "score": 0,
            "quality": 0,
            "status": "IGNORE",
            "reasons": [],
            "red_flags": [reason],
            "components": {},
        }

    def _atr_compression(self, candles: Sequence[CandleBar]) -> float:
        cur = atr(candles, 14)
        base = atr(candles[:-14] if len(candles) > 50 else candles, min(50, len(candles) - 1)) or 1e-9
        ratio = cur / base
        if ratio <= 0.35:
            return 95.0
        if ratio <= 0.55:
            return 82.0
        if ratio <= 0.75:
            return 65.0
        if ratio <= 1.0:
            return 40.0
        return max(0.0, 25 - (ratio - 1) * 20)

    def _range_compression(self, candles: Sequence[CandleBar]) -> float:
        window = candles[-24:]
        hi = max(c.high for c in window)
        lo = min(c.low for c in window)
        cur_range = (hi - lo) / (window[-1].close or 1e-9) * 100
        longer = candles[-80:] if len(candles) >= 80 else candles
        avg_ranges = []
        step = 12
        for i in range(0, len(longer) - 12, step):
            w = longer[i : i + 12]
            avg_ranges.append((max(c.high for c in w) - min(c.low for c in w)) / (w[-1].close or 1e-9) * 100)
        avg = sum(avg_ranges) / len(avg_ranges) if avg_ranges else cur_range or 1e-9
        ratio = cur_range / (avg or 1e-9)
        if ratio <= 0.25:
            return 95.0
        if ratio <= 0.4:
            return 85.0
        if ratio <= 0.6:
            return 70.0
        return max(0.0, 50 - ratio * 30)

    def _accumulation(self, candles: Sequence[CandleBar]) -> float:
        return float(self.pump._accumulation_score(candles))  # noqa: SLF001

    def _volume_growth(self, candles: Sequence[CandleBar]) -> float:
        if len(candles) < 40:
            return 0.0
        early = sum(c.volume for c in candles[-40:-20]) / 20
        late = sum(c.volume for c in candles[-20:]) / 20
        if early <= 0:
            return 0.0
        ratio = late / early
        # Price flat preference
        p0 = candles[-40].close or 1e-9
        p1 = candles[-1].close
        price_chg = abs(p1 - p0) / p0 * 100
        score = min(100.0, ratio * 25)
        if price_chg < 5 and ratio >= 2:
            score = min(100.0, score + 20)
        return score

    def _structure_prep(self, candles: Sequence[CandleBar]) -> float:
        swings = self.structure.find_swings(candles)
        sweeps = self.liquidity.detect_sweep(candles, swings)
        bos = self.structure.detect_bos(candles, swings)
        score = 30.0
        if sweeps:
            score += 30
        if bos:
            score += 25
        # higher lows
        lows = [s.price for s in swings if s.type == "swing_low" and s.price]
        if len(lows) >= 2 and lows[-1] > lows[-2]:
            score += 15
        return min(100.0, score)

    def _whale_score(
        self,
        whale_buys: Optional[list[dict[str, Any]]],
        candles: Sequence[CandleBar],
    ) -> float:
        if whale_buys:
            values = [float(w.get("value") or 0) for w in whale_buys]
            big = [v for v in values if v >= 20_000]
            if not big:
                return 40.0
            return min(100.0, 50 + len(big) * 10 + min(30, sum(big) / 100_000))
        # Heuristic: volume spikes as whale proxy
        vols = [c.volume for c in candles[-30:]]
        if not vols:
            return 20.0
        avg = sum(vols) / len(vols)
        spikes = sum(1 for v in vols if avg and v > avg * 5)
        return min(100.0, 30 + spikes * 15)

    def _estimate_buy_pressure(self, candles: Sequence[CandleBar]) -> float:
        buy = sum(c.volume for c in candles[-20:] if c.bullish)
        sell = sum(c.volume for c in candles[-20:] if c.bearish)
        denom = buy + sell or 1e-9
        return buy / denom

    def _false_pump_flags(
        self,
        candles: Sequence[CandleBar],
        vol: dict,
        spread_pct: Optional[float],
    ) -> list[str]:
        flags: list[str] = []
        last = candles[-1]
        prev = candles[-2] if len(candles) > 1 else last
        move = abs(last.close - prev.close) / (prev.close or 1e-9) * 100
        if move >= 40 and vol["rv"] < 2:
            flags.append("Single candle extension without volume")
        if last.range > 0 and (last.high - max(last.open, last.close)) / last.range > 0.6 and last.bullish:
            flags.append("Large upper wick")
        if last.bullish and last.volume < (sum(c.volume for c in candles[-10:]) / 10):
            flags.append("Price up on falling volume")
        if spread_pct is not None and spread_pct >= 2:
            flags.append("Wide spread")
        return flags

    def _quality_score(
        self,
        pump_score: int,
        flags: list[str],
        liq: float,
        spread_pct: Optional[float],
    ) -> int:
        q = float(pump_score)
        q -= len(flags) * 12
        if liq < 40:
            q -= 10
        if spread_pct and spread_pct > 0.5:
            q -= 8
        return int(max(0, min(100, round(q))))

    def _recent_move_pct(self, candles: Sequence[CandleBar], lookback: int = 24) -> float:
        if len(candles) < lookback:
            return 0.0
        a = candles[-lookback].close or 1e-9
        b = candles[-1].close
        return (b - a) / a * 100
