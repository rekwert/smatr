"""Signal Card readiness — Idea quality around Sweep/FVG/OB/OI/Delta.

BOS is a light confirmation, not the foundation.
Setup = core idea score. Execution = entry readiness now.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

LifecycleStatus = Literal[
    "IGNORE",
    "WATCH",
    "SETUP_FORMING",
    "ENTRY_ZONE",
    "ENTRY_READY",
    "IN_POSITION",
    "TP1_HIT",
    "TP2_HIT",
    "INVALIDATED",
]

STATUS_META: dict[str, dict[str, str]] = {
    "IGNORE": {"emoji": "⚪", "ru": "Игнорировать", "hint": "Слабый сценарий"},
    "WATCH": {"emoji": "🟡", "ru": "Наблюдение", "hint": "Есть идея — ждать"},
    "SETUP_FORMING": {"emoji": "🔵", "ru": "Сетап формируется", "hint": "Точка входа собирается"},
    "ENTRY_ZONE": {"emoji": "🟣", "ru": "Зона входа", "hint": "Цена у Ideal Entry"},
    "ENTRY_READY": {"emoji": "🟢", "ru": "Готов к входу", "hint": "Можно искать вход"},
    "IN_POSITION": {"emoji": "🟠", "ru": "В позиции", "hint": "Сделка открыта"},
    "TP1_HIT": {"emoji": "🟢", "ru": "TP1 достигнут", "hint": "Частичная фиксация"},
    "TP2_HIT": {"emoji": "🟢", "ru": "TP2 достигнут", "hint": "Цель 2 взята"},
    "INVALIDATED": {"emoji": "🔴", "ru": "Сценарий отменён", "hint": "Идея сломана"},
}

# Primary idea score — Sweep/Imbalance/OB first; BOS is confirmation only
SETUP_WEIGHTS = {
    "liquidity_sweep": 20,
    "fvg": 18,
    "order_block": 15,
    "oi": 15,
    "orderflow": 15,
    "volume": 8,
    "zone_align": 5,
    "market_phase": 2,
    "bos": 3,
}

# Entry-now filters (still separate from idea quality)
EXECUTION_WEIGHTS = {
    "volume": 25,
    "oi": 20,
    "orderflow": 25,
    "zone_align": 15,
    "orderbook": 10,
    "spread": 5,
}

OVERALL_SETUP_W = 0.70
OVERALL_EXEC_W = 0.30

# Display order = priority of the thesis
CONFIRMED_SHORT = {
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

EXEC_BUDGET = {
    "volume": 20,
    "oi": 18,
    "orderflow": 22,
    "current_price": 15,
    "spread": 15,
    "funding": 10,
}

def _wavg(components: dict[str, float], weights: dict[str, int]) -> int:
    total = 0.0
    wsum = 0.0
    for key, w in weights.items():
        total += float(components.get(key, 0.0)) * w
        wsum += w
    return int(round(total / wsum)) if wsum else 0


def _phase_setup_score(direction: str, phase: str) -> float:
    """How well market phase supports the trade idea."""
    if direction == "LONG":
        return {"Accumulation": 90.0, "Markup": 70.0, "Distribution": 25.0, "Markdown": 15.0}.get(
            phase, 45.0
        )
    return {"Distribution": 90.0, "Markdown": 70.0, "Accumulation": 25.0, "Markup": 15.0}.get(
        phase, 45.0
    )


def compute_setup_score(
    components: dict[str, float],
    *,
    direction: str,
    pd: Optional[dict[str, Any]] = None,
    phase: str = "",
) -> int:
    """Idea score: Sweep + FVG + OB + OI + Delta first; BOS is light confirm."""
    orderflow = float(
        components.get("orderflow")
        if components.get("orderflow") is not None
        else (float(components.get("volume") or 0) * 0.55 + float(components.get("oi") or 0) * 0.45)
    )
    enriched = {
        "liquidity_sweep": float(components.get("liquidity_sweep") or 0),
        "fvg": float(components.get("fvg") or 0),
        "order_block": float(components.get("order_block") or 0),
        "oi": float(components.get("oi") or 0),
        "orderflow": orderflow,
        "volume": float(components.get("volume") or 0),
        "zone_align": _zone_align_score(direction, pd or {}),
        "market_phase": _phase_setup_score(direction, phase),
        "bos": float(components.get("bos") or 0),
    }
    score = _wavg(enriched, SETUP_WEIGHTS)
    # Soft floors: Sweep+imbalance is ideal; FVG+OB without Sweep still watchable
    sweep_ok = enriched["liquidity_sweep"] >= 55
    imbalance_ok = enriched["fvg"] >= 50 or enriched["order_block"] >= 50
    flow_ok = enriched["oi"] >= 50 or enriched["orderflow"] >= 50 or enriched["volume"] >= 55
    strong_core = (
        enriched["liquidity_sweep"] >= 70
        and enriched["fvg"] >= 70
        and enriched["order_block"] >= 70
    )
    if strong_core:
        score = max(score, 74)
        if flow_ok:
            score = max(score, 78)
    elif sweep_ok and imbalance_ok:
        score = max(score, 62)
        if flow_ok:
            score = max(score, 68)
    elif imbalance_ok and flow_ok:
        # No sweep yet — still a candidate (WATCH floor ≥55)
        score = max(score, 55)
    elif imbalance_ok:
        score = max(score, 52)
    return max(0, min(100, score))


def score_to_stars(score: int) -> str:
    filled = max(0, min(5, int(round(max(0, score) / 20))))
    return "★" * filled + "☆" * (5 - filled)


def light(score: float, good: float = 70, mid: float = 40) -> str:
    if score >= good:
        return "🟢"
    if score >= mid:
        return "🟡"
    return "🔴"


def _zone_align_score(direction: str, pd: dict[str, Any]) -> float:
    zone = (pd or {}).get("zone")
    if direction == "LONG":
        if zone == "discount":
            return 90.0
        if zone == "equilibrium":
            return 55.0
        return 15.0 if zone == "premium" else 40.0
    if zone == "premium":
        return 90.0
    if zone == "equilibrium":
        return 55.0
    return 15.0 if zone == "discount" else 40.0


def zone_explanation(direction: str, pd: Optional[dict[str, Any]]) -> Optional[str]:
    zone = (pd or {}).get("zone")
    if direction == "SHORT" and zone == "discount":
        return (
            "Цена находится в нижней части текущего диапазона (Discount). "
            "Для SHORT предпочтительнее дождаться отката к Premium Zone или Order Block."
        )
    if direction == "LONG" and zone == "premium":
        return (
            "Цена находится в верхней части текущего диапазона (Premium). "
            "Для LONG лучше дождаться отката в Discount Zone."
        )
    if direction == "SHORT" and zone == "premium":
        return "Цена в Premium Zone — для SHORT это предпочтительная область входа."
    if direction == "LONG" and zone == "discount":
        return "Цена в Discount Zone — для LONG это предпочтительная область входа."
    return None


def build_execution_components(
    components: dict[str, float],
    *,
    direction: str,
    pd: Optional[dict[str, Any]] = None,
    orderbook_score: Optional[float] = None,
) -> dict[str, float]:
    orderflow = float(
        components.get("orderflow")
        if components.get("orderflow") is not None
        else (float(components.get("volume") or 0) * 0.55 + float(components.get("oi") or 0) * 0.45)
    )
    spread = float(components.get("spread") if components.get("spread") is not None else 50.0)
    return {
        "volume": float(components.get("volume") or 0),
        "oi": float(components.get("oi") or 0),
        "orderflow": orderflow,
        "zone_align": _zone_align_score(direction, pd or {}),
        "orderbook": float(
            orderbook_score
            if orderbook_score is not None
            else components.get("orderbook")
            if components.get("orderbook") is not None
            else 25.0
        ),
        "spread": spread,
    }


def ideal_entry_from_pd(
    direction: str,
    pd: Optional[dict[str, Any]],
    zones: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """SHORT → Premium (mid..high); LONG → Discount (low..mid)."""
    pd = pd or {}
    zones = zones or {}
    high, low, mid = pd.get("high"), pd.get("low"), pd.get("mid")
    ideal_low = ideal_high = alt_low = alt_high = None
    source = "range"
    obs = zones.get("order_blocks") or []

    if direction == "SHORT":
        if mid is not None and high is not None:
            ideal_low, ideal_high = float(mid), float(high)
            source = "premium_zone"
        bear = [o for o in obs if isinstance(o, dict) and "bearish" in str(o.get("type") or "")]
        if bear:
            o = bear[-1]
            alt_low = float(o.get("bottom") or o.get("price") or 0)
            alt_high = float(o.get("top") or o.get("price") or alt_low)
            if ideal_low is None and alt_low:
                ideal_low, ideal_high, source = alt_low, alt_high, "bearish_ob"
    else:
        if low is not None and mid is not None:
            ideal_low, ideal_high = float(low), float(mid)
            source = "discount_zone"
        bull = [o for o in obs if isinstance(o, dict) and "bullish" in str(o.get("type") or "")]
        if bull:
            o = bull[-1]
            alt_low = float(o.get("bottom") or o.get("price") or 0)
            alt_high = float(o.get("top") or o.get("price") or alt_low)
            if ideal_low is None and alt_high:
                ideal_low, ideal_high, source = alt_low, alt_high, "bullish_ob"

    ideal = None
    if ideal_low is not None and ideal_high is not None:
        ideal = (ideal_low + ideal_high) / 2
    return {
        "ideal_entry": round(ideal, 8) if ideal is not None else None,
        "ideal_entry_low": round(ideal_low, 8) if ideal_low is not None else None,
        "ideal_entry_high": round(ideal_high, 8) if ideal_high is not None else None,
        "alternative_entry_low": round(alt_low, 8) if alt_low else None,
        "alternative_entry_high": round(alt_high, 8) if alt_high else None,
        "ideal_source": source,
        "pd_zone": pd.get("zone"),
        "range_high": high,
        "range_low": low,
        "range_mid": mid,
    }


def compute_timing(
    direction: str,
    current: Optional[float],
    ideal_low: Optional[float],
    ideal_high: Optional[float],
) -> dict[str, str]:
    if current is None or ideal_low is None or ideal_high is None:
        return {
            "timing": "Optimal",
            "timing_emoji": "🟡",
            "timing_ru": "Нет Ideal Entry",
            "timing_reason": "Недостаточно данных",
        }
    mid = (ideal_low + ideal_high) / 2 or 1e-12
    buf = mid * 0.003
    if direction == "SHORT":
        if current < ideal_low - buf:
            return {
                "timing": "Late",
                "timing_emoji": "🔴",
                "timing_ru": "Поздно",
                "timing_reason": "Цена уже в Discount. Ждём ретест Premium / OB.",
            }
        if ideal_low - buf <= current <= ideal_high + buf:
            return {
                "timing": "Optimal",
                "timing_emoji": "🟢",
                "timing_ru": "Оптимально",
                "timing_reason": "Цена в Ideal Entry Zone.",
            }
        return {
            "timing": "Early",
            "timing_emoji": "🟢",
            "timing_ru": "Рано",
            "timing_reason": "Цена выше Ideal Entry — ждём подход.",
        }
    if current > ideal_high + buf:
        return {
            "timing": "Late",
            "timing_emoji": "🔴",
            "timing_ru": "Поздно",
            "timing_reason": "Цена уже в Premium. Ждём ретест Discount / OB.",
        }
    if ideal_low - buf <= current <= ideal_high + buf:
        return {
            "timing": "Optimal",
            "timing_emoji": "🟢",
            "timing_ru": "Оптимально",
            "timing_reason": "Цена в Ideal Entry Zone.",
        }
    return {
        "timing": "Early",
        "timing_emoji": "🟢",
        "timing_ru": "Рано",
        "timing_reason": "Цена ниже Ideal Entry — ждём подход.",
    }


def compute_distance_to_ideal(
    direction: str,
    current: Optional[float],
    ideal: dict[str, Any],
) -> dict[str, Any]:
    ideal_mid = ideal.get("ideal_entry")
    low = ideal.get("ideal_entry_low")
    high = ideal.get("ideal_entry_high")
    if current is None or ideal_mid is None:
        return {
            "current_price": current,
            "ideal_entry": ideal_mid,
            "ideal_entry_low": low,
            "ideal_entry_high": high,
            "distance_pct": None,
            "distance_label": "Нет Ideal Entry",
            "near_ideal": False,
        }

    # Positive => Ideal выше текущей цены (для SHORT = нужно откат вверх)
    dist = (float(ideal_mid) - float(current)) / float(current) * 100
    abs_d = abs(dist)
    near = False
    if low is not None and high is not None:
        near = float(low) * 0.997 <= float(current) <= float(high) * 1.003

    if near:
        label = "Цена в Ideal Entry Zone"
    elif direction == "SHORT":
        if dist > 0:
            label = f"До Ideal Entry (Premium) +{abs_d:.2f}% — ждём откат вверх"
        else:
            label = f"Ideal Entry ниже на {abs_d:.2f}% — поздно для нового шорта"
    else:
        if dist < 0:
            label = f"До Ideal Entry (Discount) {abs_d:.2f}% вниз — ждём откат"
        else:
            label = f"Ideal Entry выше на {abs_d:.2f}% — поздно для нового лонга"

    return {
        "current_price": current,
        "ideal_entry": ideal_mid,
        "ideal_entry_low": low,
        "ideal_entry_high": high,
        "alternative_entry_low": ideal.get("alternative_entry_low"),
        "alternative_entry_high": ideal.get("alternative_entry_high"),
        "ideal_source": ideal.get("ideal_source"),
        "distance_pct": round(dist, 3),
        "distance_label": label,
        "near_ideal": near,
        "pd_zone": ideal.get("pd_zone"),
        "range_high": ideal.get("range_high"),
        "range_low": ideal.get("range_low"),
        "range_mid": ideal.get("range_mid"),
    }


def execution_breakdown_points(
    exec_c: dict[str, float],
    *,
    timing: str,
    near_ideal: bool,
) -> dict[str, Any]:
    def pts(raw: float, budget_n: int) -> int:
        return int(max(0, min(budget_n, round(float(raw) / 100 * budget_n))))

    volume_pts = pts(exec_c.get("volume") or 0, EXEC_BUDGET["volume"])
    oi_pts = pts(exec_c.get("oi") or 0, EXEC_BUDGET["oi"])
    orderflow_pts = pts(
        exec_c.get("orderflow") if exec_c.get("orderflow") is not None else exec_c.get("orderbook") or 0,
        EXEC_BUDGET["orderflow"],
    )
    if timing == "Optimal" or near_ideal:
        price_pts = EXEC_BUDGET["current_price"]
    elif timing == "Early":
        price_pts = int(EXEC_BUDGET["current_price"] * 0.6)
    else:
        price_pts = int(EXEC_BUDGET["current_price"] * 0.25)
    spread_pts = pts(exec_c.get("spread") or 50.0, EXEC_BUDGET["spread"])

    parts = {
        "Volume": {"points": volume_pts, "max": EXEC_BUDGET["volume"]},
        "Open Interest": {"points": oi_pts, "max": EXEC_BUDGET["oi"]},
        "Order Flow": {"points": orderflow_pts, "max": EXEC_BUDGET["orderflow"]},
        "Current Price": {"points": price_pts, "max": EXEC_BUDGET["current_price"]},
        "Spread": {"points": spread_pts, "max": EXEC_BUDGET["spread"]},
        "Funding": {"points": int(EXEC_BUDGET["funding"] * 0.7), "max": EXEC_BUDGET["funding"]},
    }
    return {"total": sum(p["points"] for p in parts.values()), "parts": parts}


def resolve_lifecycle(
    setup_score: int,
    execution_score: int,
    *,
    sequence_valid: bool = False,
    invalidated: bool = False,
    near_ideal: bool = False,
    timing: str = "Optimal",
) -> LifecycleStatus:
    if invalidated:
        return "INVALIDATED"
    if setup_score < 50:
        return "IGNORE"
    if setup_score >= 70 and execution_score >= 70:
        return "ENTRY_READY"
    # Late (already in discount for SHORT) — never pretend ENTRY_ZONE
    if near_ideal and setup_score >= 70 and execution_score >= 35 and timing != "Late":
        return "ENTRY_ZONE"
    if setup_score >= 70 and execution_score >= 40:
        return "SETUP_FORMING"
    # Soft-floor / forming ideas: WATCH from 50+
    if setup_score >= 50 or sequence_valid:
        return "WATCH"
    return "IGNORE"


def build_waiting_for(
    checklist: dict[str, bool],
    *,
    direction: str,
    near_ideal: bool = False,
    timing: str = "Optimal",
) -> list[dict[str, Any]]:
    flow = (
        "Order Flow Buy Confirmation"
        if direction == "LONG"
        else "Order Flow Sell Confirmation"
    )
    zone_label = (
        "Цена в Ideal Entry (Premium / OB)"
        if direction == "SHORT"
        else "Цена в Ideal Entry (Discount / OB)"
    )
    return [
        {"key": "volume", "label": "Volume Spike >2x", "done": bool(checklist.get("volume"))},
        {"key": "oi", "label": "OI +5-10%", "done": bool(checklist.get("oi"))},
        {"key": "entry_zone", "label": zone_label, "done": near_ideal or timing == "Optimal"},
        {
            "key": "orderflow",
            "label": flow,
            "done": bool(checklist.get("volume")) and bool(checklist.get("oi")),
        },
        {"key": "timing", "label": f"Timing: {timing}", "done": timing == "Optimal"},
    ]


def build_confirmed_short(checklist: dict[str, bool], direction: str) -> list[str]:
    """Confirmed factors in thesis priority — Sweep first, BOS last."""
    out: list[str] = []
    for key in (
        "liquidity_sweep",
        "fvg",
        "order_block",
        "oi",
        "orderflow",
        "volume",
        "impulse_speed",
        "post_impulse",
        "bos",
        "htf_trend",
    ):
        if checklist.get(key):
            label = CONFIRMED_SHORT.get(key, key)
            if key == "htf_trend":
                label = f"{label} {direction}"
            if key == "bos":
                label = "BOS (подтверждение)"
            out.append(label)
    return out


def infer_market_phase(
    direction: str,
    components: dict[str, float],
    pd: Optional[dict[str, Any]] = None,
    regime: Optional[dict[str, Any]] = None,
) -> dict[str, str]:
    vol = float(components.get("volume") or 0)
    sweep = float(components.get("liquidity_sweep") or 0)
    if regime and regime.get("wyckoff_phase"):
        phase = str(regime["wyckoff_phase"])
    elif direction == "LONG":
        phase = "Markup" if vol >= 55 and sweep >= 60 else "Accumulation"
    else:
        # Low volume decline after liquidity grab ≈ Distribution; strong vol = Markdown
        phase = "Markdown" if vol >= 55 else "Distribution"
    ru = {
        "Accumulation": "Накопление (Accumulation)",
        "Distribution": "Распределение (Distribution)",
        "Markup": "Рост (Markup)",
        "Markdown": "Снижение (Markdown)",
    }
    return {"phase": phase, "phase_ru": ru.get(phase, phase)}


def scenario_risk_pct(
    *,
    setup_score: int,
    execution_score: int,
    direction: str,
    pd: Optional[dict[str, Any]],
    timing: str = "Optimal",
    age_sec: Optional[float] = None,
) -> int:
    risk = 20.0
    risk += max(0, 70 - execution_score) * 0.4
    risk += max(0, 60 - setup_score) * 0.2
    zone = (pd or {}).get("zone")
    if direction == "SHORT" and zone == "discount":
        risk += 15
    if direction == "LONG" and zone == "premium":
        risk += 15
    if timing == "Late":
        risk += 12
    if age_sec is not None:
        if age_sec > 3600:
            risk += 15
        elif age_sec > 900:
            risk += 8
    return int(max(5, min(92, round(risk))))


def freshness_from_age(age_sec: Optional[float]) -> dict[str, str]:
    if age_sec is None:
        return {"freshness": "unknown", "freshness_ru": "нет данных", "age_label": "—"}
    mins = int(age_sec // 60)
    if age_sec < 300:
        fr, fru = "high", "высокая"
    elif age_sec < 1800:
        fr, fru = "medium", "средняя"
    else:
        fr, fru = "low", "низкая"
    if mins < 1:
        age_label = f"{int(age_sec)} сек. назад"
    elif mins < 60:
        age_label = f"{mins} мин. назад"
    else:
        age_label = f"{mins // 60} ч {mins % 60} мин. назад"
    return {"freshness": fr, "freshness_ru": fru, "age_label": age_label}


def build_action(
    status: LifecycleStatus,
    waiting: list[dict[str, Any]],
    *,
    zone_note: Optional[str] = None,
    timing: str = "Optimal",
    phase: str = "",
) -> dict[str, Any]:
    pending = [w["label"] for w in waiting if not w["done"]]
    if status == "ENTRY_READY":
        return {
            "code": "ENTER",
            "emoji": "🟢",
            "title": "Можно искать вход",
            "reason": "Все ключевые фильтры подтверждены.",
            "bullets": ["Условия исполнения на месте", "Сверяй Entry / Stop / RR"],
        }
    if status == "ENTRY_ZONE":
        return {
            "code": "WAIT_TRIGGER",
            "emoji": "🟣",
            "title": "Цена в Ideal Entry — ждём триггер",
            "reason": "Цена в зоне интереса, но Execution ещё не подтверждён.",
            "bullets": pending[:4] or ["Ждать Volume / OI / Order Flow"],
        }
    if status == "INVALIDATED":
        return {
            "code": "CANCEL",
            "emoji": "🔴",
            "title": "Сценарий отменён",
            "reason": "Структура или стоп больше не валидны.",
            "bullets": ["Не входить по старому плану", "Ждать новую структуру"],
        }
    if status == "IGNORE":
        return {
            "code": "IGNORE",
            "emoji": "⚪",
            "title": "Игнорировать",
            "reason": "Сетап слишком слабый.",
            "bullets": ["Сетап слишком слабый"],
        }

    # Late / Markdown / Discount SHORT → WAIT RETEST (not fake ENTRY ZONE)
    if timing == "Late" or phase == "Markdown" or (zone_note and "отката" in zone_note):
        return {
            "code": "WAIT_RETEST",
            "emoji": "🟡",
            "title": "WAIT RETEST",
            "reason": zone_note
            or "Цена уже в менее выгодной зоне. Ждём ретест Ideal Entry (Premium/OB).",
            "bullets": pending[:4] or ["Ждать ретест Ideal Entry"],
        }
    return {
        "code": "WAIT",
        "emoji": "🟡",
        "title": "Сейчас не входить",
        "reason": zone_note or "Не хватает подтверждений исполнения.",
        "bullets": pending[:4] or ["Ждать подтверждений"],
    }


def build_ai_conclusion(
    *,
    direction: str,
    status: LifecycleStatus,
    setup_score: int,
    execution_score: int,
    timing: str,
    phase: str,
) -> str:
    side = "бычья" if direction == "LONG" else "медвежья"
    if status == "ENTRY_READY":
        return f"{side.capitalize()} структура подтверждена. Timing {timing}. Можно искать вход."
    if status == "INVALIDATED":
        return "Сценарий сломан — уровни больше не актуальны."
    if status == "IGNORE":
        return "Структура недостаточна для торгового сценария."
    if timing == "Optimal" and execution_score < 70:
        return (
            "Цена находится в хорошей зоне входа, однако отсутствует подтверждение "
            f"со стороны объёма и Order Flow (Execution {execution_score}). "
            "Ждём Volume Spike / Delta, а не новую точку по времени."
        )
    if phase == "Markdown" and direction == "SHORT" and timing == "Late":
        return (
            f"Фаза Markdown: новый SHORT осторожнее. Structure {setup_score}, "
            f"Execution {execution_score}, Timing Late. "
            f"Лучше ждать ретест Premium/OB, а не догонять снижение."
        )
    if phase == "Markup" and direction == "LONG" and timing == "Late":
        return (
            f"Фаза Markup: новый LONG осторожнее. Structure {setup_score}, "
            f"Execution {execution_score}. Лучше ждать ретест Discount/OB."
        )
    if timing == "Late":
        return (
            f"Структура {side} (Setup {setup_score}), но Timing Late — "
            f"ждём ретест Ideal Entry (Execution {execution_score})."
        )
    return (
        f"Структура {side} (Setup {setup_score}). Timing {timing}. "
        f"Не хватает подтверждений исполнения (Execution {execution_score}): "
        f"объём / OI / Order Flow."
    )


def build_ai_verdict(
    *,
    status: LifecycleStatus,
    timing: str,
    setup_score: int,
    execution_score: int,
) -> str:
    if status == "ENTRY_READY":
        return "🟢 Все условия выполнены. Можно искать вход."
    if status == "INVALIDATED":
        return "🔴 Сценарий отменён."
    if timing == "Late":
        return "🟡 Хорошая структура. Ждём ретест Ideal Entry."
    if setup_score >= 70 and execution_score < 50:
        return "🟡 Хорошая структура. Ждём подтверждение продавцов/покупателей."
    return "🟡 Наблюдение. Сетап ещё собирается."


def traffic_lights(
    setup_score: int,
    execution_score: int,
    breakdown: dict[str, Any],
    timing: str,
    scenario_risk: int,
) -> dict[str, str]:
    of = (breakdown.get("parts") or {}).get("Order Flow", {})
    of_score = (of.get("points") or 0) / max(1, of.get("max") or 20) * 100
    return {
        "structure": light(setup_score),
        "execution": light(execution_score),
        "orderflow": light(of_score),
        "timing": "🟢" if timing == "Optimal" else ("🟡" if timing == "Early" else "🔴"),
        "risk": "🟢" if scenario_risk < 35 else ("🟡" if scenario_risk < 60 else "🔴"),
    }


def build_why_no_entry(
    *,
    status: LifecycleStatus,
    direction: str,
    timing: str,
    pd: Optional[dict[str, Any]],
    distance_pct: Optional[float],
    near_ideal: bool,
) -> Optional[dict[str, Any]]:
    """One consolidated block — replaces duplicated Late / Discount / WAIT texts."""
    if status in ("ENTRY_READY", "IN_POSITION", "TP1_HIT", "TP2_HIT"):
        return None
    if status == "INVALIDATED":
        return {
            "title": "Сценарий отменён",
            "bullets": ["Структура сломана", "Не входить по старому плану"],
        }
    if status == "IGNORE":
        return {
            "title": "Почему сейчас нет входа",
            "bullets": ["Structure слишком слабый", "Сетап не торгуемый"],
        }

    bullets: list[str] = []
    zone = (pd or {}).get("zone")
    abs_d = abs(float(distance_pct)) if distance_pct is not None else None

    if timing == "Late" and direction == "SHORT":
        if abs_d is not None:
            bullets.append(f"Цена уже прошла вниз ~{abs_d:.1f}%")
        if zone == "discount":
            bullets.append("Сейчас находится в Discount Zone")
        bullets.append("Для SHORT нужен откат в Premium / OB")
        bullets.append("Timing = Late")
    elif timing == "Late" and direction == "LONG":
        if abs_d is not None:
            bullets.append(f"Цена уже прошла вверх ~{abs_d:.1f}%")
        if zone == "premium":
            bullets.append("Сейчас находится в Premium Zone")
        bullets.append("Для LONG нужен откат в Discount / OB")
        bullets.append("Timing = Late")
    elif not near_ideal:
        if abs_d is not None and distance_pct is not None:
            side = "выше" if distance_pct > 0 else "ниже"
            bullets.append(f"Ideal Entry {side} текущей цены на ~{abs_d:.1f}%")
        bullets.append("Ждём подход цены к Ideal Entry")
        bullets.append(f"Timing = {timing}")
    else:
        bullets.append("Цена у Ideal Entry, но Execution ещё слабый")
        bullets.append("Ждём Volume / OI / Order Flow")

    return {"title": "Почему сейчас нет входа", "bullets": bullets}


def build_range_scale(
    *,
    current: Optional[float],
    ideal: dict[str, Any],
) -> Optional[dict[str, Any]]:
    high = ideal.get("range_high")
    low = ideal.get("range_low")
    mid = ideal.get("range_mid")
    if high is None or low is None:
        return None
    hi, lo = float(high), float(low)
    span = hi - lo
    if span <= 0:
        return None

    def pct(v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        return round(max(0.0, min(100.0, (float(v) - lo) / span * 100)), 1)

    return {
        "high": hi,
        "low": lo,
        "mid": float(mid) if mid is not None else (hi + lo) / 2,
        "price": current,
        "ideal_low": ideal.get("ideal_entry_low"),
        "ideal_high": ideal.get("ideal_entry_high"),
        "ideal_mid": ideal.get("ideal_entry"),
        "price_pct": pct(current),
        "ideal_low_pct": pct(ideal.get("ideal_entry_low")),
        "ideal_high_pct": pct(ideal.get("ideal_entry_high")),
        "ideal_mid_pct": pct(ideal.get("ideal_entry")),
        "mid_pct": pct(mid if mid is not None else (hi + lo) / 2),
        "zone": ideal.get("pd_zone"),
    }


def compute_probabilities(
    *,
    setup_score: int,
    execution_score: int,
    timing: str,
    near_ideal: bool,
    scenario_risk: int,
) -> dict[str, int]:
    """Scenario = идея ещё жива; Entry Now = можно ли входить прямо сейчас."""
    scenario = setup_score * 0.72 + (100 - scenario_risk) * 0.18 + execution_score * 0.10
    if timing == "Late":
        scenario -= 6
    scenario = int(max(8, min(92, round(scenario))))

    entry_now = execution_score * 0.55 + (70 if near_ideal else 25) * 0.25
    if timing == "Optimal":
        entry_now += 12
    elif timing == "Early":
        entry_now += 4
    else:
        entry_now -= 18
    entry_now = entry_now * (setup_score / 100)
    entry_now = int(max(3, min(95, round(entry_now))))
    return {
        "scenario_probability": scenario,
        "entry_probability_now": entry_now,
        "probability": scenario,  # public alias = scenario survival
    }


def normalize_trade_plan(
    *,
    direction: str,
    plan_entry: Optional[float],
    current: Optional[float],
    stop: Optional[float],
    tp1: Optional[float],
    tp2: Optional[float],
    ideal: dict[str, Any],
    risk_reward: Optional[float] = None,
) -> dict[str, Any]:
    """Align Stop/TP to Ideal Entry. SHORT stop must be ABOVE entry; LONG below."""
    entry = plan_entry
    if entry is None:
        return {
            "entry": None,
            "stop": stop,
            "tp1": tp1,
            "tp2": tp2,
            "risk_reward": risk_reward,
            "risk_pct": None,
            "plan_valid": False,
            "plan_note": "Нет Ideal Entry для плана",
        }

    entry_f = float(entry)
    atr_proxy = entry_f * 0.012
    range_high = ideal.get("range_high")
    range_low = ideal.get("range_low")
    ideal_high = ideal.get("ideal_entry_high")
    ideal_low = ideal.get("ideal_entry_low")

    if direction == "SHORT":
        candidates = [entry_f + atr_proxy * 1.15]
        if stop is not None and float(stop) > entry_f:
            candidates.append(float(stop))
        if ideal_high is not None:
            candidates.append(float(ideal_high) * 1.002)
        if range_high is not None:
            candidates.append(max(float(range_high) * 0.998, entry_f + atr_proxy))
        stop_f = max(candidates)
        # Hard floor: stop always above entry
        stop_f = max(stop_f, entry_f * 1.008)
        risk = max(stop_f - entry_f, atr_proxy * 0.35)
        tp1_f = entry_f - risk * 2.0
        tp2_f = entry_f - risk * 3.0
        if range_low is not None:
            tp2_f = max(tp2_f, float(range_low))
    else:
        candidates = [entry_f - atr_proxy * 1.15]
        if stop is not None and float(stop) < entry_f:
            candidates.append(float(stop))
        if ideal_low is not None:
            candidates.append(float(ideal_low) * 0.998)
        if range_low is not None:
            candidates.append(min(float(range_low) * 1.002, entry_f - atr_proxy))
        stop_f = min(candidates)
        stop_f = min(stop_f, entry_f * 0.992)
        risk = max(entry_f - stop_f, atr_proxy * 0.35)
        tp1_f = entry_f + risk * 2.0
        tp2_f = entry_f + risk * 3.0
        if range_high is not None:
            tp2_f = min(tp2_f, float(range_high))

    rr = round(abs(tp2_f - entry_f) / risk, 2) if risk else risk_reward
    risk_pct = round(risk / entry_f * 100, 2) if entry_f else None
    plan_valid = (direction == "SHORT" and stop_f > entry_f) or (
        direction == "LONG" and stop_f < entry_f
    )
    return {
        "entry": round(entry_f, 8),
        "stop": round(stop_f, 8),
        "tp1": round(tp1_f, 8),
        "tp2": round(tp2_f, 8),
        "risk_reward": rr,
        "risk_pct": risk_pct,
        "plan_valid": plan_valid,
        "plan_note": (
            None
            if plan_valid
            else "Уровни плана скорректированы: Stop должен быть с правильной стороны от Entry"
        ),
        "invalidation_level": round(stop_f, 8),
    }


def build_invalidation(
    *,
    direction: str,
    stop: Optional[float],
    ideal: dict[str, Any],
    checklist: dict[str, bool],
    current: Optional[float] = None,
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    # Prefer structural invalidation above Ideal/Premium for SHORT
    if direction == "SHORT":
        items.append({"key": "bos_up", "label": "BOS вверх против сценария"})
        inv_level = stop
        if inv_level is None:
            inv_level = ideal.get("ideal_entry_high") or ideal.get("range_high")
        if inv_level is not None:
            items.append(
                {
                    "key": "hold_above",
                    "label": f"Закрепление выше {round(float(inv_level), 6)}",
                }
            )
            if current is not None and float(current) > float(inv_level):
                items.insert(
                    0,
                    {
                        "key": "already_broken",
                        "label": "Цена уже выше уровня инвалидации — сценарий под вопросом",
                    },
                )
    else:
        items.append({"key": "bos_down", "label": "BOS вниз против сценария"})
        inv_level = stop
        if inv_level is None:
            inv_level = ideal.get("ideal_entry_low") or ideal.get("range_low")
        if inv_level is not None:
            items.append(
                {
                    "key": "hold_below",
                    "label": f"Закрепление ниже {round(float(inv_level), 6)}",
                }
            )
            if current is not None and float(current) < float(inv_level):
                items.insert(
                    0,
                    {
                        "key": "already_broken",
                        "label": "Цена уже ниже уровня инвалидации — сценарий под вопросом",
                    },
                )
    items.append({"key": "oi_fade", "label": "OI снижается на продолжении движения"})
    flow = "Buy Delta > Sell Delta" if direction == "SHORT" else "Sell Delta > Buy Delta"
    items.append({"key": "delta_against", "label": flow})
    if not checklist.get("htf_trend"):
        items.append({"key": "htf_flip", "label": "Смена HTF тренда против идеи"})
    return items


def build_confidence_drivers(
    *,
    components: dict[str, float],
    breakdown: dict[str, Any],
    timing: str,
    setup_score: int,
) -> list[dict[str, Any]]:
    drivers: list[dict[str, Any]] = []
    # Setup positives / gaps — Sweep/FVG/OB/OI first; BOS last
    for key, label, w in (
        ("liquidity_sweep", "Sweep", 18),
        ("fvg", "FVG", 14),
        ("order_block", "Order Block", 12),
        ("oi", "OI", 12),
        ("orderflow", "Order Flow", 12),
        ("volume", "Volume", 8),
        ("impulse_speed", "Impulse", 8),
        ("bos", "BOS", 4),
    ):
        raw = float(components.get(key) or 0)
        impact = int(round((raw - 50) / 50 * w))
        if abs(impact) >= 3:
            drivers.append(
                {
                    "key": key,
                    "label": label,
                    "impact": impact,
                    "direction": "up" if impact > 0 else "down",
                }
            )

    parts = breakdown.get("parts") or {}
    for name, key, scale in (
        ("Order Flow", "orderflow", 18),
        ("Volume", "volume", 14),
        ("Open Interest", "oi", 12),
        ("Current Price", "current_price", 10),
    ):
        part = parts.get(name) or {}
        pts = float(part.get("points") or 0)
        mx = float(part.get("max") or 1) or 1
        ratio = pts / mx
        impact = int(round((ratio - 0.5) * 2 * scale))
        if abs(impact) >= 4:
            drivers.append(
                {
                    "key": key,
                    "label": name if name != "Open Interest" else "OI",
                    "impact": impact,
                    "direction": "up" if impact > 0 else "down",
                }
            )

    if timing == "Late":
        drivers.append({"key": "timing", "label": "Timing", "impact": -22, "direction": "down"})
    elif timing == "Early":
        drivers.append({"key": "timing", "label": "Timing", "impact": -6, "direction": "down"})
    elif timing == "Optimal":
        drivers.append({"key": "timing", "label": "Timing", "impact": 10, "direction": "up"})

    if setup_score < 55:
        drivers.append(
            {"key": "structure", "label": "Structure", "impact": -14, "direction": "down"}
        )

    drivers.sort(key=lambda d: abs(int(d["impact"])), reverse=True)
    return drivers[:7]


def build_next_trigger(
    *,
    status: LifecycleStatus,
    direction: str,
    waiting: list[dict[str, Any]],
    ideal: dict[str, Any],
    current: Optional[float],
    near_ideal: bool = False,
    timing: str = "Optimal",
) -> Optional[dict[str, Any]]:
    if status in ("ENTRY_READY", "INVALIDATED", "IGNORE", "IN_POSITION"):
        return None

    in_zone = near_ideal or timing == "Optimal"
    conditions: list[str] = []

    if in_zone:
        # Price already at Ideal Entry — ask for confirmations, not a return
        for w in waiting:
            if w.get("done"):
                continue
            key = str(w.get("key") or "")
            label = str(w.get("label") or "")
            if key in ("entry_zone", "timing"):
                continue
            if "Ideal Entry" in label or "цена верн" in label.lower():
                continue
            conditions.append(label)
        if direction == "LONG":
            conditions = [
                c
                for c in conditions
                if "Sell" not in c
            ] or ["Volume Spike >2x", "Buy Delta / Order Flow"]
            if not any("Volume" in c for c in conditions):
                conditions.insert(0, "Volume Spike >2x")
            if not any("Delta" in c or "Order Flow" in c or "Buy" in c for c in conditions):
                conditions.append("Buy Delta")
        else:
            conditions = conditions or ["Volume Spike >2x", "Sell Delta / Order Flow"]
            if not any("Volume" in c for c in conditions):
                conditions.insert(0, "Volume Spike >2x")
            if not any("Delta" in c or "Order Flow" in c or "Sell" in c for c in conditions):
                conditions.append("Sell Delta")
        title = "Следующее подтверждение"
        target = "ENTRY_READY"
    else:
        for w in waiting:
            if not w.get("done"):
                conditions.append(str(w.get("label")))
        if direction == "SHORT" and ideal.get("ideal_entry") and current is not None:
            if float(current) < float(ideal.get("ideal_entry_low") or ideal["ideal_entry"]):
                lo = ideal.get("ideal_entry_low") or ideal["ideal_entry"]
                conditions.insert(0, f"Цена вернётся в {round(float(lo), 6)}")
        if direction == "LONG" and ideal.get("ideal_entry") and current is not None:
            if float(current) > float(ideal.get("ideal_entry_high") or ideal["ideal_entry"]):
                hi = ideal.get("ideal_entry_high") or ideal["ideal_entry"]
                conditions.insert(0, f"Цена вернётся в {round(float(hi), 6)}")
        title = "Следующее событие"
        target = "ENTRY_READY" if status in ("ENTRY_ZONE", "SETUP_FORMING") else "ENTRY_ZONE"
        if status == "WATCH":
            target = "SETUP_FORMING"

    seen: set[str] = set()
    uniq: list[str] = []
    for c in conditions:
        if c and c not in seen:
            seen.add(c)
            uniq.append(c)

    return {
        "title": title,
        "if_conditions": uniq[:4] or ["Подтверждение объёмом и Order Flow"],
        "from_status": status,
        "to_status": target,
        "note": "Статус изменится автоматически при выполнении условий",
    }


def compute_edge_score(
    *,
    direction: str,
    components: dict[str, float],
    checklist: dict[str, bool],
    pd: Optional[dict[str, Any]],
    risk_reward: Optional[float],
    liquidity_quality: Optional[int],
    volume_24h: Optional[float],
    similar_winrate: Optional[float] = None,
    setup_score: int,
    timing: str,
) -> dict[str, Any]:
    """Why this coin deserves attention among hundreds — inefficiency / SMC edge."""
    reasons: list[str] = []
    score = 35.0

    liq = liquidity_quality if liquidity_quality is not None else 50
    # Prefer thin / mid liquidity for inefficiency hunting
    if volume_24h is not None and volume_24h < 5_000_000:
        score += 14
        reasons.append("Неликвидная монета")
    elif liq < 45:
        score += 12
        reasons.append("Неликвидная монета")
    elif liq < 60:
        score += 6
        reasons.append("Средняя ликвидность — есть неэффективность")

    oi = float(components.get("oi") or 0)
    if oi >= 55:
        score += 10
        reasons.append("OI выше среднего")
    elif oi >= 40:
        score += 5

    if checklist.get("liquidity_sweep") or float(components.get("liquidity_sweep") or 0) >= 55:
        score += 12
        reasons.append("Sweep")
    if checklist.get("order_block") or float(components.get("order_block") or 0) >= 55:
        score += 8
        reasons.append("Order Block")
    if checklist.get("fvg") or float(components.get("fvg") or 0) >= 55:
        score += 8
        reasons.append("FVG")
    if checklist.get("bos") or float(components.get("bos") or 0) >= 55:
        score += 3
        reasons.append("BOS (confirm)")

    zone = (pd or {}).get("zone")
    if direction == "LONG" and zone == "discount":
        score += 10
        reasons.append("Discount")
    elif direction == "SHORT" and zone == "premium":
        score += 10
        reasons.append("Premium")
    elif direction == "LONG" and zone == "premium":
        score -= 8
    elif direction == "SHORT" and zone == "discount":
        score -= 6

    if risk_reward is not None and float(risk_reward) >= 2.5:
        score += 10
        reasons.append(f"RR >{float(risk_reward):.1f}" if float(risk_reward) < 3 else "RR >2.5")
    elif risk_reward is not None and float(risk_reward) >= 2.0:
        score += 5
        reasons.append("RR ≥2")

    wr = similar_winrate
    if wr is not None:
        if wr >= 60:
            score += 8
            reasons.append(f"Журнальный WinRate {wr:.0f}%")
    else:
        # Proxy until trade journal exists — do NOT claim historical winrate
        proxy = min(78.0, max(42.0, 40 + setup_score * 0.4))
        if proxy >= 60:
            score += 4
            reasons.append(f"Оценка по качеству сетапа ~{proxy:.0f}%")

    if timing == "Optimal":
        score += 4
    elif timing == "Late":
        score -= 10

    score_i = int(max(5, min(95, round(score))))
    # Keep unique reasons, max 7
    uniq: list[str] = []
    for r in reasons:
        if r not in uniq:
            uniq.append(r)
    return {
        "edge_score": score_i,
        "edge_stars": score_to_stars(score_i),
        "edge_reasons": [f"+ {r}" for r in uniq[:7]],
        "edge_hint": (
            "Сильный edge среди рынка"
            if score_i >= 75
            else "Умеренный edge"
            if score_i >= 55
            else "Слабый edge — смотри другие идеи"
        ),
    }


def build_replay_seed(status: LifecycleStatus, *, at: Optional[datetime] = None) -> list[dict[str, Any]]:
    stamp = (at or datetime.now(timezone.utc)).strftime("%H:%M")
    meta = STATUS_META.get(status, {})
    return [
        {
            "time": stamp,
            "status": status,
            "label": meta.get("ru") or status.replace("_", " "),
            "emoji": meta.get("emoji") or "🟡",
        }
    ]


def merge_replay(
    previous: Optional[dict[str, Any]],
    *,
    status: LifecycleStatus,
    at: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Append lifecycle transitions for Replay timeline."""
    hist = list((previous or {}).get("replay") or [])
    stamp = (at or datetime.now(timezone.utc)).strftime("%H:%M")
    meta = STATUS_META.get(status, {})
    event = {
        "time": stamp,
        "status": status,
        "label": meta.get("ru") or status.replace("_", " "),
        "emoji": meta.get("emoji") or "🟡",
    }
    if not hist:
        return [event]
    last = hist[0] if hist and isinstance(hist[0], dict) else None
    # hist is newest-first after we prepend
    if last and last.get("status") == status:
        return hist[:20]
    return [event] + hist[:19]


def compute_liquidity_quality(
    *,
    exec_c: dict[str, float],
    breakdown: dict[str, Any],
    volume_24h: Optional[float] = None,
) -> dict[str, Any]:
    parts = breakdown.get("parts") or {}
    spread_p = (parts.get("Spread") or {}).get("points") or 5
    spread_m = (parts.get("Spread") or {}).get("max") or 10
    of_p = (parts.get("Order Flow") or {}).get("points") or 0
    of_m = (parts.get("Order Flow") or {}).get("max") or 20
    vol = float(exec_c.get("volume") or 0)
    ob = float(exec_c.get("orderbook") or 0)

    score = (
        (float(spread_p) / max(1, float(spread_m))) * 25
        + (float(of_p) / max(1, float(of_m))) * 20
        + (vol / 100) * 30
        + (ob / 100) * 15
    )
    if volume_24h is not None:
        # Soft bump for deep markets
        if volume_24h >= 50_000_000:
            score += 10
        elif volume_24h >= 10_000_000:
            score += 6
        elif volume_24h < 1_000_000:
            score -= 12
    score_i = int(max(5, min(95, round(score))))
    return {
        "liquidity_quality": score_i,
        "liquidity_stars": score_to_stars(score_i),
        "liquidity_hint": (
            "Низкий риск проскальзывания"
            if score_i >= 70
            else "Средний риск проскальзывания"
            if score_i >= 45
            else "Высокий риск проскальзывания на входе"
        ),
    }


def compute_chasing_risk(
    *,
    timing: str,
    distance_pct: Optional[float],
    near_ideal: bool,
    direction: str,
    pd: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Risk of chasing a move already underway (Late ≈ high)."""
    risk = 25.0
    if timing == "Late":
        risk = 78.0
    elif timing == "Early":
        risk = 28.0
    elif timing == "Optimal" or near_ideal:
        risk = 18.0

    if distance_pct is not None:
        abs_d = abs(float(distance_pct))
        if timing == "Late":
            risk += min(18.0, abs_d * 1.2)
        elif abs_d > 3 and not near_ideal:
            risk += min(12.0, abs_d * 0.8)

    zone = (pd or {}).get("zone")
    if direction == "SHORT" and zone == "discount" and timing == "Late":
        risk += 6
    if direction == "LONG" and zone == "premium" and timing == "Late":
        risk += 6

    score = int(max(5, min(95, round(risk))))
    if score >= 70:
        level, level_ru = "HIGH", "Высокий"
    elif score >= 40:
        level, level_ru = "MEDIUM", "Средний"
    else:
        level, level_ru = "LOW", "Низкий"
    return {
        "chasing_risk": score,
        "chasing_level": level,
        "chasing_level_ru": level_ru,
        "chasing_hint": (
            "Догоняете движение — лучше ждать ретест"
            if level == "HIGH"
            else "Умеренный риск догона"
            if level == "MEDIUM"
            else "Не похоже на догон движения"
        ),
    }


def infer_smart_money_activity(
    *,
    direction: str,
    components: dict[str, float],
    checklist: dict[str, bool],
    phase: str,
    pd: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Proxy for institutional footprint: Accumulation / Distribution / Inactive."""
    sweep = float(components.get("liquidity_sweep") or 0)
    bos = float(components.get("bos") or 0)
    ob = float(components.get("order_block") or 0)
    fvg = float(components.get("fvg") or 0)
    vol = float(components.get("volume") or 0)
    oi = float(components.get("oi") or 0)
    htf = float(components.get("htf_trend") or 0)

    footprint = (
        sweep * 0.22
        + bos * 0.2
        + ob * 0.18
        + fvg * 0.12
        + vol * 0.12
        + oi * 0.08
        + htf * 0.08
    )
    score = int(max(5, min(95, round(footprint))))

    confirmed_n = sum(
        1
        for k in ("liquidity_sweep", "bos", "order_block", "fvg", "htf_trend")
        if checklist.get(k)
    )

    zone = (pd or {}).get("zone")
    if footprint < 42 or confirmed_n < 2:
        activity = "Inactive"
        activity_ru = "Нет явной активности"
    elif direction == "LONG" or phase in ("Accumulation", "Markup"):
        if zone == "discount" or phase == "Accumulation" or (sweep >= 60 and bos >= 55):
            activity = "Accumulation"
            activity_ru = "Накопление"
        else:
            activity = "Accumulation"
            activity_ru = "Накопление"
    elif direction == "SHORT" or phase in ("Distribution", "Markdown"):
        activity = "Distribution"
        activity_ru = "Распределение"
    else:
        activity = "Inactive"
        activity_ru = "Нет явной активности"

    # Directional override from phase when structure is strong
    if footprint >= 55:
        if phase == "Accumulation":
            activity, activity_ru = "Accumulation", "Накопление"
        elif phase == "Distribution":
            activity, activity_ru = "Distribution", "Распределение"
        elif phase == "Markdown" and direction == "SHORT":
            activity, activity_ru = "Distribution", "Распределение"
        elif phase == "Markup" and direction == "LONG":
            activity, activity_ru = "Accumulation", "Накопление"

    return {
        "smart_money_activity": activity,
        "smart_money_ru": activity_ru,
        "smart_money_score": score,
        "smart_money_stars": score_to_stars(score),
        "smart_money_hint": (
            "Признаки участия крупных игроков"
            if activity != "Inactive"
            else "Крупные игроки явно не видны"
        ),
    }


def diff_score_history(
    previous: Optional[dict[str, Any]],
    current: dict[str, Any],
    *,
    at: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Append change events vs previous snapshot (for memory re-scans)."""
    hist = list((previous or {}).get("score_history") or [])
    if not previous:
        return hist[-12:]
    stamp = (at or datetime.now(timezone.utc)).strftime("%H:%M")
    events: list[dict[str, Any]] = []

    def add(field: str, old: Any, new: Any, reason: str) -> None:
        if old == new:
            return
        events.append(
            {
                "time": stamp,
                "field": field,
                "from": old,
                "to": new,
                "reason": reason,
            }
        )

    add(
        "Execution",
        previous.get("execution_score"),
        current.get("execution_score"),
        _exec_change_reason(previous, current),
    )
    add(
        "Structure",
        previous.get("setup_score"),
        current.get("setup_score"),
        "Обновление SMC-компонентов",
    )
    add(
        "Timing",
        previous.get("timing"),
        current.get("timing"),
        current.get("timing_reason") or "Сдвиг цены относительно Ideal Entry",
    )
    add(
        "Status",
        previous.get("lifecycle_status"),
        current.get("lifecycle_status"),
        (current.get("action") or {}).get("reason") or "Смена фазы сетапа",
    )
    hist = events + hist
    return hist[:12]


def _exec_change_reason(prev: dict[str, Any], cur: dict[str, Any]) -> str:
    prev_parts = ((prev.get("execution_breakdown") or {}).get("parts")) or {}
    cur_parts = ((cur.get("execution_breakdown") or {}).get("parts")) or {}
    deltas: list[tuple[int, str]] = []
    for name in ("Open Interest", "Volume", "Order Flow", "Current Price"):
        a = int((prev_parts.get(name) or {}).get("points") or 0)
        b = int((cur_parts.get(name) or {}).get("points") or 0)
        if b != a:
            sign = "+" if b > a else ""
            short = "OI" if name == "Open Interest" else name
            deltas.append((abs(b - a), f"{sign}{short} {a}→{b}"))
    deltas.sort(reverse=True)
    if deltas:
        return deltas[0][1]
    pe, ce = int(prev.get("execution_score") or 0), int(cur.get("execution_score") or 0)
    if ce > pe:
        return "Улучшение фильтров исполнения"
    if ce < pe:
        return "Ослабление фильтров исполнения"
    return "Переоценка Execution"


def build_readiness_payload(
    *,
    direction: str,
    components: dict[str, float],
    checklist: dict[str, bool],
    sequence_valid: bool,
    pd: Optional[dict[str, Any]] = None,
    zones: Optional[dict[str, Any]] = None,
    regime: Optional[dict[str, Any]] = None,
    orderbook_score: Optional[float] = None,
    invalidated: bool = False,
    entry: Optional[float] = None,
    current_price: Optional[float] = None,
    created_at: Optional[datetime] = None,
    tp1: Optional[float] = None,
    tp2: Optional[float] = None,
    stop: Optional[float] = None,
    risk_reward: Optional[float] = None,
    volume_24h: Optional[float] = None,
    previous: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    # Phase first (feeds Setup weights)
    phase = infer_market_phase(direction, components, pd=pd, regime=regime)
    setup_score = compute_setup_score(
        components, direction=direction, pd=pd, phase=phase["phase"]
    )
    exec_c = build_execution_components(
        components, direction=direction, pd=pd, orderbook_score=orderbook_score
    )

    ideal = ideal_entry_from_pd(direction, pd, zones)
    current = current_price if current_price is not None else entry
    dist = compute_distance_to_ideal(direction, current, ideal)
    timing_info = compute_timing(
        direction,
        current,
        ideal.get("ideal_entry_low"),
        ideal.get("ideal_entry_high"),
    )
    timing = timing_info["timing"]
    near_ideal = bool(dist.get("near_ideal"))

    breakdown = execution_breakdown_points(exec_c, timing=timing, near_ideal=near_ideal)
    # Transparent total + slight zone_align blend
    execution_score = int(
        round(0.85 * breakdown["total"] + 0.15 * float(exec_c.get("zone_align") or 0))
    )
    execution_score = max(0, min(100, execution_score))
    overall = int(round(OVERALL_SETUP_W * setup_score + OVERALL_EXEC_W * execution_score))

    status = resolve_lifecycle(
        setup_score,
        execution_score,
        sequence_valid=sequence_valid or setup_score >= 70,
        invalidated=invalidated,
        near_ideal=near_ideal,
        timing=timing,
    )
    meta = STATUS_META[status]
    confirmed = build_confirmed_short(checklist, direction)
    waiting = build_waiting_for(
        checklist, direction=direction, near_ideal=near_ideal, timing=timing
    )
    zone_note = zone_explanation(direction, pd)

    now = datetime.now(timezone.utc)
    created = created_at or now
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    age_sec = max(0.0, (now - created).total_seconds())
    fresh = freshness_from_age(age_sec)
    risk_pct = scenario_risk_pct(
        setup_score=setup_score,
        execution_score=execution_score,
        direction=direction,
        pd=pd,
        timing=timing,
        age_sec=age_sec,
    )
    action = build_action(
        status,
        waiting,
        zone_note=zone_note,
        timing=timing,
        phase=phase["phase"],
    )
    ai_conclusion = build_ai_conclusion(
        direction=direction,
        status=status,
        setup_score=setup_score,
        execution_score=execution_score,
        timing=timing,
        phase=phase["phase"],
    )
    ai_verdict = build_ai_verdict(
        status=status,
        timing=timing,
        setup_score=setup_score,
        execution_score=execution_score,
    )
    lights = traffic_lights(setup_score, execution_score, breakdown, timing, risk_pct)
    probs = compute_probabilities(
        setup_score=setup_score,
        execution_score=execution_score,
        timing=timing,
        near_ideal=near_ideal,
        scenario_risk=risk_pct,
    )
    why = build_why_no_entry(
        status=status,
        direction=direction,
        timing=timing,
        pd=pd,
        distance_pct=dist.get("distance_pct"),
        near_ideal=near_ideal,
    )
    range_scale = build_range_scale(current=current, ideal=ideal)

    # Plan entry = Ideal Entry; Stop/TP must match direction (SHORT stop ABOVE entry)
    display_entry = ideal.get("ideal_entry") or entry
    plan = normalize_trade_plan(
        direction=direction,
        plan_entry=display_entry,
        current=current,
        stop=stop,
        tp1=tp1,
        tp2=tp2,
        ideal=ideal,
        risk_reward=risk_reward,
    )
    plan_stop = plan.get("stop")
    plan_tp1 = plan.get("tp1")
    plan_tp2 = plan.get("tp2")
    plan_rr = plan.get("risk_reward")

    invalidation = build_invalidation(
        direction=direction,
        stop=plan_stop,
        ideal=ideal,
        checklist=checklist,
        current=current,
    )
    drivers = build_confidence_drivers(
        components=components,
        breakdown=breakdown,
        timing=timing,
        setup_score=setup_score,
    )
    next_trigger = build_next_trigger(
        status=status,
        direction=direction,
        waiting=waiting,
        ideal=ideal,
        current=current,
        near_ideal=near_ideal,
        timing=timing,
    )
    liq = compute_liquidity_quality(
        exec_c=exec_c, breakdown=breakdown, volume_24h=volume_24h
    )
    chasing = compute_chasing_risk(
        timing=timing,
        distance_pct=dist.get("distance_pct"),
        near_ideal=near_ideal,
        direction=direction,
        pd=pd,
    )
    smart = infer_smart_money_activity(
        direction=direction,
        components=components,
        checklist=checklist,
        phase=phase["phase"],
        pd=pd,
    )

    edge = compute_edge_score(
        direction=direction,
        components=components,
        checklist=checklist,
        pd=pd,
        risk_reward=plan_rr,
        liquidity_quality=liq.get("liquidity_quality"),
        volume_24h=volume_24h,
        setup_score=setup_score,
        timing=timing,
    )
    replay = merge_replay(previous, status=status, at=now)

    missing_items = [w["label"] for w in waiting if not w["done"]]
    # Prefer consolidated why-block over duplicating zone_note in missing
    if why and why.get("bullets"):
        missing_items = list(why["bullets"])

    payload = {
        "setup_score": setup_score,
        "execution_score": execution_score,
        "overall_score": overall,
        "overall_formula": "Setup*70% + Execution*30%",
        "setup_stars": score_to_stars(setup_score),
        "execution_stars": score_to_stars(execution_score),
        "probability": probs["scenario_probability"],
        "scenario_probability": probs["scenario_probability"],
        "entry_probability_now": probs["entry_probability_now"],
        "lifecycle_status": status,
        "lifecycle_emoji": meta["emoji"],
        "lifecycle_ru": meta["ru"],
        "lifecycle_hint": meta["hint"],
        "phase": phase["phase"],
        "phase_ru": phase["phase_ru"],
        "timing": timing_info["timing"],
        "timing_emoji": timing_info["timing_emoji"],
        "timing_ru": timing_info["timing_ru"],
        "timing_reason": timing_info["timing_reason"],
        "traffic_lights": lights,
        "execution_breakdown": breakdown,
        "ideal_entry": ideal.get("ideal_entry"),
        "ideal_entry_low": ideal.get("ideal_entry_low"),
        "ideal_entry_high": ideal.get("ideal_entry_high"),
        "alternative_entry_low": ideal.get("alternative_entry_low"),
        "alternative_entry_high": ideal.get("alternative_entry_high"),
        "ideal_source": ideal.get("ideal_source"),
        "pd_zone": ideal.get("pd_zone"),
        "range_high": ideal.get("range_high"),
        "range_low": ideal.get("range_low"),
        "range_mid": ideal.get("range_mid"),
        "range_scale": range_scale,
        "confirmed": confirmed,
        "missing_items": missing_items,
        "waiting_for": waiting,
        "next_steps": [w["label"] for w in waiting if not w["done"]],
        "ai_comment": ai_conclusion,
        "ai_conclusion": ai_conclusion,
        "ai_verdict": ai_verdict,
        "zone_note": None if why else zone_note,
        "why_no_entry": why,
        "invalidation": invalidation,
        "confidence_drivers": drivers,
        "next_trigger": next_trigger,
        "liquidity_quality": liq["liquidity_quality"],
        "liquidity_stars": liq["liquidity_stars"],
        "liquidity_hint": liq["liquidity_hint"],
        "chasing_risk": chasing["chasing_risk"],
        "chasing_level": chasing["chasing_level"],
        "chasing_level_ru": chasing["chasing_level_ru"],
        "chasing_hint": chasing["chasing_hint"],
        "smart_money_activity": smart["smart_money_activity"],
        "smart_money_ru": smart["smart_money_ru"],
        "smart_money_score": smart["smart_money_score"],
        "smart_money_stars": smart["smart_money_stars"],
        "smart_money_hint": smart["smart_money_hint"],
        "edge_score": edge["edge_score"],
        "edge_stars": edge["edge_stars"],
        "edge_reasons": edge["edge_reasons"],
        "edge_hint": edge["edge_hint"],
        "replay": replay,
        "risk_label": "Высокий" if risk_pct >= 60 else "Средний" if risk_pct >= 35 else "Низкий",
        "scenario_risk_pct": risk_pct,
        "current_price": dist.get("current_price"),
        "distance_pct": dist.get("distance_pct"),
        "distance_label": dist.get("distance_label"),
        "near_entry": near_ideal,
        "action": action,
        "status_reason": action.get("reason"),
        "freshness": fresh["freshness"],
        "freshness_ru": fresh["freshness_ru"],
        "age_sec": int(age_sec),
        "age_label": fresh["age_label"],
        "reeval_sec": 60,
        "tp1": plan_tp1,
        "tp2": plan_tp2,
        "stop": plan_stop,
        "entry": plan.get("entry") or display_entry,
        "risk_reward": plan_rr,
        "risk_pct": plan.get("risk_pct"),
        "plan_valid": plan.get("plan_valid"),
        "plan_note": plan.get("plan_note"),
        "invalidation_level": plan.get("invalidation_level") or plan_stop,
        "execution_components": exec_c,
        "progress": [],
    }
    payload["score_history"] = diff_score_history(previous, payload, at=now)
    return payload
