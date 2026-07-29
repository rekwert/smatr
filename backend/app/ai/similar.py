"""Similar historical setups via fingerprint matching (Part 5 §4 / MVP without vector DB)."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Signal
from app.services import memory_store


def fingerprint_from_signal(signal: dict[str, Any]) -> set[str]:
    tags: set[str] = set()
    checklist = (signal.get("reason") or {}).get("checklist") or {}
    for k, v in checklist.items():
        if v:
            tags.add(k)
    for item in (signal.get("reason") or {}).get("found") or []:
        low = str(item).lower()
        if "sweep" in low:
            tags.add("liquidity_sweep")
        if "bos" in low:
            tags.add("bos")
        if "fvg" in low:
            tags.add("fvg")
        if "order block" in low or "ob" == low:
            tags.add("order_block")
        if "volume" in low:
            tags.add("volume")
    tags.add(f"dir:{(signal.get('direction') or '').upper()}")
    tags.add(f"tf:{signal.get('timeframe')}")
    tags.add(f"type:{signal.get('signal_type') or 'smc'}")
    return tags


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _row_view(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    return {
        "id": getattr(row, "id", None),
        "symbol": getattr(row, "symbol", None),
        "direction": getattr(row, "direction", None),
        "timeframe": getattr(row, "timeframe", None),
        "signal_type": getattr(row, "signal_type", None),
        "score": getattr(row, "score", None),
        "risk_reward": getattr(row, "risk_reward", None),
        "reason": getattr(row, "reason", None) or {},
    }


async def find_similar_setups(
    db: Optional[AsyncSession],
    signal: dict[str, Any],
    limit: int = 200,
) -> dict[str, Any]:
    fp = fingerprint_from_signal(signal)
    rows: list[Any] = []
    if db is not None:
        try:
            rows = list(
                (await db.execute(select(Signal).order_by(desc(Signal.created_at)).limit(limit * 3)))
                .scalars()
                .all()
            )
        except Exception:  # noqa: BLE001
            rows = []
    if not rows:
        rows = memory_store.list_signals(min_score=0, limit=limit * 3)

    scored: list[tuple[float, Any]] = []
    for row in rows:
        view = _row_view(row)
        if signal.get("id") and view.get("id") == signal.get("id"):
            continue
        other = {
            "direction": view.get("direction"),
            "timeframe": view.get("timeframe"),
            "signal_type": view.get("signal_type"),
            "reason": view.get("reason") or {},
        }
        sim = jaccard(fp, fingerprint_from_signal(other))
        if sim >= 0.4:
            scored.append((sim, view))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:limit]

    if top:
        avg_score = sum(float(s.get("score") or 0) for _, s in top) / len(top)
        up_prob = min(85.0, max(40.0, 45 + (avg_score - 50) * 0.5))
        avg_rr = sum(float(s.get("risk_reward") or 2.0) for _, s in top) / len(top)
    else:
        up_prob, avg_rr = 50.0, 2.0

    return {
        "sample_size": len(top),
        "fingerprint": sorted(fp),
        "up_probability_pct": round(up_prob, 1),
        "average_rr": round(avg_rr, 2),
        "avg_hold_hours_est": 7,
        "note": (
            "MVP similarity uses feature Jaccard over stored signals. "
            "Vector/pgvector enrichment comes later."
        ),
        "examples": [
            {
                "id": s.get("id"),
                "symbol": s.get("symbol"),
                "score": s.get("score"),
                "similarity": round(sim, 2),
            }
            for sim, s in top[:10]
        ],
    }
