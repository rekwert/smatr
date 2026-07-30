"""Inefficiency trading profile — what makes THIS mispricing special.

Playbook (product thesis):
1. Hunt mid/low liquidity where discovery is weak (not BTC tape).
2. Event: Sweep / flash displacement leaves FVG + defending OB.
3. Location: Discount for LONG / Premium for SHORT.
4. Edge = rarity & extremity of the mispricing (not “can I click buy”).
5. Execution = Volume RV + OI + Order Flow to actually enter.
"""

from __future__ import annotations

from typing import Any, Optional


def _f(components: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(components.get(key) if components.get(key) is not None else default)
    except (TypeError, ValueError):
        return default


def estimate_rv_from_volume_score(volume_score: float) -> float:
    """Invert VolumeAnalyzer score→RV mapping (approx)."""
    s = float(volume_score or 0)
    if s <= 0:
        return 0.0
    if s < 30:
        return max(0.05, s / 30.0)
    if s < 60:
        # 40 + (rv-1)*20  → rv = 1 + (s-40)/20
        return max(1.0, 1.0 + (s - 40.0) / 20.0)
    if s < 85:
        # 60 + (rv-2)*8 → rv = 2 + (s-60)/8
        return 2.0 + (s - 60.0) / 8.0
    return min(12.0, 5.0 + (s - 85.0) / 2.0)


def compute_inefficiency_profile(
    *,
    direction: str,
    components: dict[str, Any],
    checklist: dict[str, bool],
    pd: Optional[dict[str, Any]] = None,
    volume_24h: Optional[float] = None,
    liquidity_quality: Optional[int] = None,
) -> dict[str, Any]:
    """Graded inefficiency metrics used by Edge + card thesis."""
    sweep = _f(components, "liquidity_sweep")
    fvg = _f(components, "fvg")
    ob = _f(components, "order_block")
    impulse = _f(components, "impulse_pct")
    impulse_bars = int(_f(components, "impulse_bars", 0) or 0)
    vol_score = _f(components, "volume")
    rv = _f(components, "relative_volume") or _f(components, "rv")
    if rv <= 0:
        rv = estimate_rv_from_volume_score(vol_score)

    zone = (pd or {}).get("zone")
    zone_ok = (direction == "LONG" and zone == "discount") or (
        direction == "SHORT" and zone == "premium"
    )

    # Thinness 0..100 (higher = more inefficient venue)
    thin = 40.0
    if volume_24h is not None:
        v = float(volume_24h)
        if v < 500_000:
            thin = 95.0
        elif v < 1_500_000:
            thin = 85.0
        elif v < 5_000_000:
            thin = 72.0
        elif v < 20_000_000:
            thin = 48.0
        else:
            thin = 22.0
    elif liquidity_quality is not None:
        thin = max(10.0, 100.0 - float(liquidity_quality))

    # Displacement extremity vs quiet tape
    if impulse >= 12:
        displace = 92.0
    elif impulse >= 8:
        displace = 78.0
    elif impulse >= 5:
        displace = 62.0
    elif impulse >= 3:
        displace = 45.0
    else:
        displace = max(10.0, impulse * 12)

    structure = (
        min(100.0, sweep) * 0.40
        + min(100.0, fvg) * 0.30
        + min(100.0, ob) * 0.30
    )

    # Event class
    if sweep >= 55 and fvg >= 50 and ob >= 50 and zone_ok:
        itype = "sweep_reclaim"
        type_ru = "Sweep → FVG → OB (reclaim)"
    elif impulse >= 8 and thin >= 60:
        itype = "flash_displacement"
        type_ru = "Flash / тонкий импульс"
    elif fvg >= 55 and zone_ok:
        itype = "imbalance_fill"
        type_ru = "Имбаланс (FVG) в зоне"
    else:
        itype = "structural"
        type_ru = "Структурный сетап"

    # Strength: thin venue × structure × displacement (not entry readiness)
    strength = thin * 0.28 + structure * 0.42 + displace * 0.30
    if zone_ok:
        strength += 6
    if rv >= 2.0:
        strength += 5  # volume ON the event validates inefficiency was real
    elif rv < 1.0:
        strength -= 8  # silent tape after “sweep” = weaker edge
    strength = int(max(5, min(98, round(strength))))

    vol_label = f"{volume_24h/1e6:.2f}M" if volume_24h is not None else "—"
    thesis_parts = [
        type_ru,
        f"тонкость {int(thin)}",
        f"смещение {impulse:.1f}%" if impulse else "смещение н/д",
        f"RV×{rv:.2f}",
        f"24h {vol_label}",
    ]
    if zone:
        thesis_parts.append(str(zone))

    missing_flow: list[str] = []
    if rv < 2.0:
        missing_flow.append(f"RV×{rv:.2f} < 2.0 (нужен всплеск на reclaim)")
    if _f(components, "oi") < 50:
        missing_flow.append("OI ещё не подтвердил интерес")
    if _f(components, "orderflow") < 50:
        missing_flow.append("Order Flow / delta слабый")

    return {
        "inefficiency_type": itype,
        "inefficiency_type_ru": type_ru,
        "inefficiency_strength": strength,
        "thinness": int(round(thin)),
        "structure_quality": int(round(structure)),
        "displacement_pct": round(impulse, 2),
        "displacement_score": int(round(displace)),
        "impulse_bars": impulse_bars,
        "relative_volume": round(rv, 2),
        "volume_24h": volume_24h,
        "zone": zone,
        "zone_aligned": zone_ok,
        "thesis": " · ".join(thesis_parts),
        "entry_blockers": missing_flow,
        "checklist_ok": bool(
            (checklist.get("liquidity_sweep") or sweep >= 55)
            and (checklist.get("fvg") or fvg >= 50)
            and (checklist.get("order_block") or ob >= 50)
        ),
    }


# Hunter / universe noise — not SMC confirms
CONFIRMED_NOISE_PREFIXES = (
    "Volume mid-band",
    "Spread",
    "Very thin book",
    "Move ",
    "Thin book",
    "New listing",
    "Low liquidity band",
    "mid-band",
)


def is_noise_confirm(text: str) -> bool:
    t = str(text or "")
    return any(t.startswith(p) or p.lower() in t.lower() for p in CONFIRMED_NOISE_PREFIXES)


def filter_confirmed_items(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if not item or is_noise_confirm(item):
            continue
        if item not in out:
            out.append(item)
    return out
