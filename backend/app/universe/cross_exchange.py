"""Cross-Exchange Inefficiency Scanner."""

from __future__ import annotations

from collections import defaultdict

from app.universe.models import CrossOpportunity, UniverseRow


def find_cross_inefficiencies(
    rows: list[UniverseRow],
    *,
    min_spread_pct: float = 1.5,
    min_volume: float = 100_000,
    limit: int = 50,
) -> list[CrossOpportunity]:
    """Same normalized symbol, price gaps across exchanges."""
    by_sym: dict[str, list[UniverseRow]] = defaultdict(list)
    for r in rows:
        if r.price <= 0 or r.volume_24h < min_volume:
            continue
        if r.symbol in {"BTCUSDT", "ETHUSDT"}:
            continue
        by_sym[r.symbol].append(r)

    opps: list[CrossOpportunity] = []
    for sym, group in by_sym.items():
        if len(group) < 2:
            continue
        low = min(group, key=lambda x: x.price)
        high = max(group, key=lambda x: x.price)
        if low.price <= 0:
            continue
        gap = (high.price - low.price) / low.price * 100
        if gap < min_spread_pct:
            continue
        # Early move hint: volume spike on one venue vs quiet on another
        vols = sorted(group, key=lambda x: x.volume_24h, reverse=True)
        note = f"Ценовой разрыв {gap:.1f}%"
        if len(vols) >= 2 and vols[0].volume_24h > vols[1].volume_24h * 3:
            note += f"; объём {vols[0].exchange} >> {vols[1].exchange}"
        opps.append(
            CrossOpportunity(
                symbol=sym,
                low_exchange=low.exchange,
                high_exchange=high.exchange,
                low_price=low.price,
                high_price=high.price,
                spread_pct=round(gap, 2),
                volume_low=low.volume_24h,
                volume_high=high.volume_24h,
                note=note,
            )
        )

    opps.sort(key=lambda o: o.spread_pct, reverse=True)
    return opps[:limit]
