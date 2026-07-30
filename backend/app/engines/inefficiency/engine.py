"""Inefficiency Engine — product core for trading market mispricings.

Ready-tool playbook (not generic SMC):
1. DETECT   — flash spike OR liquidity sweep leaving imbalance on thin tape
2. LOCATE   — price in reclaim zone (Discount/OB for LONG, Premium/OB for SHORT)
3. CONFIRM  — relative volume ≥2× on reclaim + order-flow proxy
4. ENTER    — defined entry / stop beyond extreme / TP toward mean
5. INVALIDATE — break of extreme or expiry of the event window

SMC Sweep/FVG/OB are confirmation layers for the reclaim path.
Flash path can stand alone when displacement is extreme vs ATR.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from app.engines.inefficiency.flash import detect_flash_inefficiency
from app.engines.inefficiency.profile import estimate_rv_from_volume_score
from app.market_data.candles import CandleBar

# Lifecycle for inefficiency product
INEFF_DETECTED = "INEFF_DETECTED"
INEFF_RECLAIMING = "INEFF_RECLAIMING"
INEFF_WAIT_VOLUME = "INEFF_WAIT_VOLUME"
INEFF_ENTRY_READY = "INEFF_ENTRY_READY"
INEFF_INVALIDATED = "INEFF_INVALIDATED"
INEFF_EXPIRED = "INEFF_EXPIRED"
INEFF_NONE = "INEFF_NONE"

MIN_FLASH_MOVE_PCT = 5.0
MIN_SWEEP_DISPLACEMENT_PCT = 2.5  # below this = noise, not inefficiency
MIN_RV_ENTRY = 2.0
MAX_EVENT_BARS = 18  # ~4.5h on 15m


def _rv(components: dict[str, Any], vol: Optional[dict[str, Any]] = None) -> float:
    if vol and vol.get("rv") is not None:
        try:
            return float(vol["rv"])
        except (TypeError, ValueError):
            pass
    for k in ("relative_volume", "rv"):
        try:
            v = float(components.get(k) or 0)
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass
    return estimate_rv_from_volume_score(float(components.get("volume") or 0))


def _thinness(volume_24h: Optional[float]) -> float:
    if volume_24h is None:
        return 50.0
    v = float(volume_24h)
    if v < 500_000:
        return 95.0
    if v < 1_500_000:
        return 85.0
    if v < 5_000_000:
        return 72.0
    if v < 20_000_000:
        return 45.0
    return 18.0


def evaluate_inefficiency(
    candles: Sequence[CandleBar],
    *,
    direction: str,
    components: dict[str, Any],
    checklist: dict[str, bool],
    pd: Optional[dict[str, Any]] = None,
    volume_24h: Optional[float] = None,
    vol: Optional[dict[str, Any]] = None,
    levels: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build inefficiency event + playbook + entry plan."""
    if len(candles) < 30:
        return _empty("Недостаточно истории")

    current = float(candles[-1].close)
    rv = _rv(components, vol)
    thin = _thinness(volume_24h)
    impulse = float(components.get("impulse_pct") or 0)
    sweep_ok = bool(checklist.get("liquidity_sweep")) or float(components.get("liquidity_sweep") or 0) >= 55
    fvg_ok = bool(checklist.get("fvg")) or float(components.get("fvg") or 0) >= 50
    ob_ok = bool(checklist.get("order_block")) or float(components.get("order_block") or 0) >= 50
    zone = (pd or {}).get("zone")
    zone_ok = (direction == "LONG" and zone == "discount") or (
        direction == "SHORT" and zone == "premium"
    )

    flash = detect_flash_inefficiency(
        candles,
        spike_pct=MIN_FLASH_MOVE_PCT,
        snapback_ratio=0.50,
    )
    flash_ok = bool(flash.get("detected")) and thin >= 40

    # Prefer flash direction when flash is the primary event
    event_direction = direction
    kind = None
    move_pct = impulse
    if flash_ok:
        kind = "flash_spike"
        event_direction = str(flash.get("direction") or direction)
        move_pct = float(flash.get("move_pct") or impulse)
    elif sweep_ok and fvg_ok and ob_ok and impulse >= MIN_SWEEP_DISPLACEMENT_PCT:
        kind = "sweep_reclaim"
        move_pct = max(impulse, float(components.get("impulse_pct") or 0))
    elif sweep_ok and fvg_ok and ob_ok and thin >= 65:
        # Thin tape + full structure, softer displacement floor
        kind = "sweep_reclaim"
        move_pct = max(impulse, 1.5)
    else:
        return {
            **_empty("Нет торгуемой неэффективности"),
            "relative_volume": round(rv, 2),
            "thinness": int(thin),
            "displacement_pct": round(impulse, 2),
            "qualifies": False,
        }

    # Align zone check to event direction
    zone_ok = (event_direction == "LONG" and zone == "discount") or (
        event_direction == "SHORT" and zone == "premium"
    ) or zone in (None, "equilibrium")

    plan = _build_plan(
        kind=kind,
        direction=event_direction,
        current=current,
        flash=flash if flash_ok else {},
        levels=levels or {},
        pd=pd or {},
        candles=candles,
    )

    near_entry = _near_entry(current, plan)
    flow_ok = (
        rv >= MIN_RV_ENTRY
        or float(components.get("orderflow") or 0) >= 55
        or float(components.get("oi") or 0) >= 55
    )
    volume_ok = rv >= MIN_RV_ENTRY

    # Invalidation / expiry
    invalidated = _is_invalidated(event_direction, current, plan, flash if flash_ok else {})
    expired = False
    if flash_ok and flash.get("bar_index") is not None:
        age_bars = len(candles) - 1 - int(flash["bar_index"])
        expired = age_bars > MAX_EVENT_BARS

    status = _resolve_status(
        invalidated=invalidated,
        expired=expired,
        near_entry=near_entry,
        volume_ok=volume_ok,
        flow_ok=flow_ok,
        flash_ok=flash_ok,
        snapback=float((flash or {}).get("snapback_ratio") or 0),
    )

    strength = _strength(
        thin=thin,
        move_pct=move_pct,
        rv=rv,
        structure=(sweep_ok and fvg_ok and ob_ok),
        zone_ok=zone_ok,
        kind=kind,
    )

    playbook = _playbook(
        status=status,
        kind=kind,
        direction=event_direction,
        near_entry=near_entry,
        volume_ok=volume_ok,
        flow_ok=flow_ok,
        rv=rv,
        plan=plan,
    )

    action = _action(status, playbook, plan)

    qualifies = (
        not invalidated
        and not expired
        and strength >= 55
        and thin >= 40
        and kind is not None
        and (flash_ok or (sweep_ok and fvg_ok and ob_ok))
    )

    type_ru = {
        "flash_spike": "Flash spike → mean reversion",
        "sweep_reclaim": "Sweep → FVG → OB reclaim",
    }.get(kind or "", "Неэффективность")

    return {
        "qualifies": qualifies,
        "inefficiency_kind": kind,
        "inefficiency_type": kind,
        "inefficiency_type_ru": type_ru,
        "inefficiency_status": status,
        "inefficiency_status_ru": _status_ru(status),
        "inefficiency_strength": strength,
        "direction": event_direction,
        "relative_volume": round(rv, 2),
        "thinness": int(round(thin)),
        "displacement_pct": round(float(move_pct), 2),
        "zone": zone,
        "zone_aligned": zone_ok,
        "near_entry": near_entry,
        "volume_ok": volume_ok,
        "flow_ok": flow_ok,
        "flash": flash if flash_ok else None,
        "plan": plan,
        "playbook": playbook,
        "action": action,
        "thesis": (
            f"{type_ru} · смещение {move_pct:.1f}% · RV×{rv:.2f} · "
            f"тонкость {int(thin)} · 24h {_vol_label(volume_24h)}"
        ),
        "entry_blockers": [s["label"] for s in playbook if not s.get("done") and s.get("required")],
        "hint": action.get("reason") or "",
    }


def _empty(reason: str) -> dict[str, Any]:
    return {
        "qualifies": False,
        "inefficiency_kind": None,
        "inefficiency_type": None,
        "inefficiency_type_ru": None,
        "inefficiency_status": INEFF_NONE,
        "inefficiency_status_ru": "Нет события",
        "inefficiency_strength": 0,
        "thesis": reason,
        "playbook": [],
        "plan": {},
        "action": {
            "code": "SKIP",
            "emoji": "⚪",
            "title": "Пропуск",
            "reason": reason,
        },
        "entry_blockers": [reason],
    }


def _vol_label(volume_24h: Optional[float]) -> str:
    if volume_24h is None:
        return "n/a"
    return f"{float(volume_24h) / 1e6:.2f}M"


def _build_plan(
    *,
    kind: str,
    direction: str,
    current: float,
    flash: dict[str, Any],
    levels: dict[str, Any],
    pd: dict[str, Any],
    candles: Sequence[CandleBar],
) -> dict[str, Any]:
    atr = _atr(candles) or current * 0.01

    if kind == "flash_spike" and flash.get("detected"):
        baseline = float(flash["baseline"])
        extreme = float(flash["extreme"])
        if direction == "SHORT":
            entry = (baseline + extreme) / 2
            entry_low = baseline
            entry_high = extreme - atr * 0.15
            stop = extreme + atr * 0.35
            tp1 = baseline
            tp2 = baseline - abs(extreme - baseline) * 0.35
        else:
            entry = (baseline + extreme) / 2
            entry_low = extreme + atr * 0.15
            entry_high = baseline
            stop = extreme - atr * 0.35
            tp1 = baseline
            tp2 = baseline + abs(baseline - extreme) * 0.35
        # Normalize SHORT stop above entry
        if direction == "SHORT":
            stop = max(stop, entry * 1.004, entry + atr * 0.25)
            entry_low, entry_high = min(entry_low, entry_high), max(entry_low, entry_high)
        else:
            stop = min(stop, entry * 0.996, entry - atr * 0.25)
            entry_low, entry_high = min(entry_low, entry_high), max(entry_low, entry_high)
    else:
        # Sweep reclaim: use SMC levels when present
        entry = float(levels.get("ideal_entry") or levels.get("entry") or current)
        stop = float(levels.get("stop") or (entry - atr * 1.2 if direction == "LONG" else entry + atr * 1.2))
        tp1 = float(levels.get("tp1") or (entry + atr * 2 if direction == "LONG" else entry - atr * 2))
        tp2 = float(levels.get("tp2") or (entry + atr * 3 if direction == "LONG" else entry - atr * 3))
        band = atr * 0.8
        if direction == "LONG":
            entry_low, entry_high = entry - band, entry + band * 0.35
            stop = min(stop, entry - atr * 0.4)
        else:
            entry_low, entry_high = entry - band * 0.35, entry + band
            stop = max(stop, entry + atr * 0.4)

    risk = abs(entry - stop)
    reward = abs(tp1 - entry)
    rr = round(reward / risk, 2) if risk > 0 else None

    return {
        "entry": round(entry, 8),
        "entry_low": round(entry_low, 8),
        "entry_high": round(entry_high, 8),
        "stop": round(stop, 8),
        "tp1": round(tp1, 8),
        "tp2": round(tp2, 8),
        "risk_reward": rr,
        "invalidation": round(stop, 8),
        "kind": kind,
    }


def _atr(candles: Sequence[CandleBar], n: int = 14) -> float:
    if len(candles) < n + 1:
        return 0.0
    trs = []
    for i in range(-n, 0):
        h = float(candles[i].high)
        l = float(candles[i].low)
        pc = float(candles[i - 1].close)
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs)


def _near_entry(current: float, plan: dict[str, Any]) -> bool:
    lo = plan.get("entry_low")
    hi = plan.get("entry_high")
    if lo is None or hi is None:
        return False
    return float(lo) <= current <= float(hi)


def _is_invalidated(
    direction: str,
    current: float,
    plan: dict[str, Any],
    flash: dict[str, Any],
) -> bool:
    stop = plan.get("stop")
    if stop is None:
        return False
    if direction == "LONG" and current < float(stop):
        return True
    if direction == "SHORT" and current > float(stop):
        return True
    if flash.get("detected"):
        extreme = float(flash.get("extreme") or 0)
        if direction == "LONG" and extreme and current < extreme * 0.997:
            # new low beyond flash floor
            if current < float(stop):
                return True
        if direction == "SHORT" and extreme and current > extreme * 1.003:
            if current > float(stop):
                return True
    return False


def _resolve_status(
    *,
    invalidated: bool,
    expired: bool,
    near_entry: bool,
    volume_ok: bool,
    flow_ok: bool,
    flash_ok: bool,
    snapback: float,
) -> str:
    if invalidated:
        return INEFF_INVALIDATED
    if expired:
        return INEFF_EXPIRED
    if near_entry and volume_ok and flow_ok:
        return INEFF_ENTRY_READY
    if near_entry and not volume_ok:
        return INEFF_WAIT_VOLUME
    if flash_ok and snapback >= 0.35:
        return INEFF_RECLAIMING
    if near_entry:
        return INEFF_WAIT_VOLUME
    return INEFF_DETECTED


def _strength(
    *,
    thin: float,
    move_pct: float,
    rv: float,
    structure: bool,
    zone_ok: bool,
    kind: Optional[str],
) -> int:
    score = thin * 0.25
    # Displacement grade
    if move_pct >= 12:
        score += 32
    elif move_pct >= 8:
        score += 26
    elif move_pct >= 5:
        score += 20
    elif move_pct >= 2.5:
        score += 12
    else:
        score += 4
    if structure:
        score += 14
    if zone_ok:
        score += 8
    if rv >= 2.5:
        score += 12
    elif rv >= 2.0:
        score += 8
    elif rv < 1.0:
        score -= 6
    if kind == "flash_spike":
        score += 4
    return int(max(5, min(98, round(score))))


def _status_ru(status: str) -> str:
    return {
        INEFF_DETECTED: "Событие найдено",
        INEFF_RECLAIMING: "Идёт возврат (snapback)",
        INEFF_WAIT_VOLUME: "Ждём объём на reclaim",
        INEFF_ENTRY_READY: "Можно искать вход",
        INEFF_INVALIDATED: "Событие сломано",
        INEFF_EXPIRED: "Окно истекло",
        INEFF_NONE: "Нет события",
    }.get(status, status)


def _playbook(
    *,
    status: str,
    kind: Optional[str],
    direction: str,
    near_entry: bool,
    volume_ok: bool,
    flow_ok: bool,
    rv: float,
    plan: dict[str, Any],
) -> list[dict[str, Any]]:
    steps = [
        {
            "key": "event",
            "label": "Событие неэффективности",
            "done": status not in (INEFF_NONE, INEFF_INVALIDATED, INEFF_EXPIRED),
            "required": True,
        },
        {
            "key": "zone",
            "label": (
                f"Цена в зоне входа {plan.get('entry_low')}–{plan.get('entry_high')}"
                if plan.get("entry_low") is not None
                else "Цена в зоне входа"
            ),
            "done": near_entry,
            "required": True,
        },
        {
            "key": "volume",
            "label": f"RV×{rv:.2f} ≥ {MIN_RV_ENTRY:.1f} на reclaim",
            "done": volume_ok,
            "required": True,
        },
        {
            "key": "flow",
            "label": "Order Flow / OI в сторону сценария",
            "done": flow_ok,
            "required": True,
        },
        {
            "key": "risk",
            "label": (
                f"Stop {plan.get('stop')} · TP1 {plan.get('tp1')} · RR {plan.get('risk_reward')}"
                if plan.get("stop") is not None
                else "План риска готов"
            ),
            "done": plan.get("stop") is not None and plan.get("tp1") is not None,
            "required": True,
        },
    ]
    if status == INEFF_INVALIDATED:
        steps.append(
            {"key": "dead", "label": "Инвалидация — не входить", "done": True, "required": False}
        )
    return steps


def synthesize_playbook(
    *,
    near_entry: bool,
    rv: float,
    flow_ok: bool,
    plan: Optional[dict[str, Any]] = None,
    status: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Playbook without candles — for API serialize of stored signals."""
    plan = plan or {}
    volume_ok = rv >= MIN_RV_ENTRY
    return _playbook(
        status=status or (INEFF_WAIT_VOLUME if near_entry else INEFF_DETECTED),
        kind="sweep_reclaim",
        direction="LONG",
        near_entry=near_entry,
        volume_ok=volume_ok,
        flow_ok=flow_ok,
        rv=rv,
        plan=plan,
    )


def _action(status: str, playbook: list[dict[str, Any]], plan: dict[str, Any]) -> dict[str, Any]:
    pending = [s["label"] for s in playbook if s.get("required") and not s.get("done")]
    if status == INEFF_ENTRY_READY:
        return {
            "code": "ENTER",
            "emoji": "🟢",
            "title": "Вход по неэффективности",
            "reason": "Зона + объём подтверждены. Работай от плана, не от рынка вдогонку.",
            "bullets": [
                f"Entry {plan.get('entry_low')}–{plan.get('entry_high')}",
                f"Stop {plan.get('stop')}",
                f"TP1 {plan.get('tp1')}",
            ],
        }
    if status == INEFF_WAIT_VOLUME:
        return {
            "code": "WAIT_VOLUME",
            "emoji": "🟡",
            "title": "Ждать объём",
            "reason": "Цена в зоне, но без RV≥2× вход — лотерея на тонком стакане.",
            "bullets": pending[:3] or ["Ждём Volume Spike"],
        }
    if status == INEFF_RECLAIMING:
        return {
            "code": "WATCH_SNAPBACK",
            "emoji": "🟡",
            "title": "Смотреть snapback",
            "reason": "Идёт возврат к базе. Не догонять — ждать зону входа.",
            "bullets": pending[:3],
        }
    if status == INEFF_INVALIDATED:
        return {
            "code": "SKIP",
            "emoji": "🔴",
            "title": "Сценарий сломан",
            "reason": "Цена пробила инвалидацию события.",
            "bullets": ["Не усреднять", "Искать новое событие"],
        }
    if status == INEFF_EXPIRED:
        return {
            "code": "SKIP",
            "emoji": "⚪",
            "title": "Окно закрыто",
            "reason": "Слишком поздно для этого flash/sweep окна.",
            "bullets": ["Идея устарела"],
        }
    return {
        "code": "WATCH",
        "emoji": "🟡",
        "title": "Наблюдать событие",
        "reason": "Неэффективность найдена — ждём reclaim в зону.",
        "bullets": pending[:3],
    }
