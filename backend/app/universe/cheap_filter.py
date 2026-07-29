"""Level 2 — Cheap Filter (ticker-only, fast)."""

from __future__ import annotations

from typing import Optional

from app.universe.models import DEFAULT_EXCLUDE, Tier, UniverseRow


def assign_tier(
    volume: float,
    age_days: Optional[float],
    *,
    tier_a_min: float = 500_000,
    tier_a_max: float = 20_000_000,
    tier_b_min: float = 100_000,
    tier_b_max: float = 500_000,
    new_listing_days: float = 30.0,
) -> Tier:
    if age_days is not None and age_days <= new_listing_days:
        return "C"
    if tier_a_min <= volume <= tier_a_max:
        return "A"
    if tier_b_min <= volume < tier_b_max:
        return "B"
    return "SKIP"


def cheap_score(row: UniverseRow) -> float:
    """0–100 fast score without candles."""
    score = 0.0
    reasons: list[str] = []

    # Prefer mid liquidity (Tier A sweet spot)
    vol = row.volume_24h
    if 500_000 <= vol <= 10_000_000:
        score += 30
        reasons.append(f"Volume mid-band {vol/1e6:.2f}M")
    elif 100_000 <= vol < 500_000:
        score += 18
        reasons.append(f"Volume low-band {vol/1e3:.0f}k")
    elif 10_000_000 < vol <= 20_000_000:
        score += 12
        reasons.append("Volume upper mid")
    else:
        score += 0

    # Spread: wider = more inefficiency (but not absurd)
    sp = row.spread_pct
    if sp is not None:
        if 0.05 <= sp <= 0.8:
            score += 20
            reasons.append(f"Spread {sp:.2f}%")
        elif sp > 0.8:
            score += 10
            reasons.append(f"Wide spread {sp:.2f}%")
        elif sp < 0.05:
            score += 5

    # Liquidity score inverted preference for hunter (42 = interesting)
    liq = row.liquidity_score
    if 25 <= liq <= 55:
        score += 20
        reasons.append(f"Liquidity {liq:.0f}/100")
    elif 55 < liq <= 70:
        score += 10
    elif liq < 25:
        score += 8
        reasons.append("Very thin book")

    # Vol expansion proxy via |24h change|
    ch = abs(float(row.change_pct_24h or 0))
    row.vol_expansion_proxy = ch
    if ch >= 8:
        score += 15
        reasons.append(f"Move {ch:.1f}% /24h")
    elif ch >= 3:
        score += 8
        reasons.append(f"Move {ch:.1f}% /24h")

    # Volume anomaly proxy: large move + mid volume
    if ch >= 5 and 500_000 <= vol <= 15_000_000:
        ratio = min(12.0, 1.0 + ch / 2)
        row.volume_ratio_proxy = ratio
        score += 10
        reasons.append(f"Vol anomaly proxy ~{ratio:.1f}x")

    # New listing boost
    if row.tier == "C" or (row.age_days is not None and row.age_days <= 30):
        score += 12
        reasons.append(f"New listing ~{row.age_days:.0f}d" if row.age_days is not None else "New listing")

    row.reasons = reasons
    return min(100.0, round(score, 1))


def apply_cheap_filter(
    rows: list[UniverseRow],
    *,
    exclude_majors: bool = True,
    exclude: Optional[set[str]] = None,
    max_candidates: int = 200,
    min_cheap_score: float = 25.0,
) -> list[UniverseRow]:
    """7000 → ~100–200 candidates."""
    ban = set(exclude or DEFAULT_EXCLUDE) if exclude_majors else set()
    filtered: list[UniverseRow] = []

    for r in rows:
        if r.symbol in ban:
            r.tier = "SKIP"
            continue
        # Hard skip mega caps by volume
        if r.volume_24h > 50_000_000:
            r.tier = "SKIP"
            continue
        if r.volume_24h < 100_000:
            r.tier = "SKIP"
            continue

        r.tier = assign_tier(r.volume_24h, r.age_days)
        if r.tier == "SKIP":
            continue
        r.cheap_score = cheap_score(r)
        if r.cheap_score < min_cheap_score:
            continue
        filtered.append(r)

    filtered.sort(key=lambda x: x.cheap_score, reverse=True)
    return filtered[:max_candidates]
