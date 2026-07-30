"""Trade journal for inefficiency setups — real WinRate feed into Edge."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import desc, select

from app.database.connection import SessionLocal
from app.database.models import Trade
from app.database.pg_health import pg_up

logger = logging.getLogger(__name__)

# In-memory fallback when Postgres is down
_MEM: list[dict[str, Any]] = []
_ID = 1

SYSTEM_USER_ID = 1


def _next_id() -> int:
    global _ID
    n = _ID
    _ID += 1
    return n


async def create_trade(
    *,
    symbol: str,
    direction: str,
    entry_price: Optional[float] = None,
    exit_price: Optional[float] = None,
    result: Optional[str] = None,  # win | loss | be | open
    result_r: Optional[float] = None,
    signal_id: Optional[int] = None,
    exchange: str = "bybit",
    setup: str = "inefficiency",
    notes: Optional[str] = None,
    inefficiency_type: Optional[str] = None,
    edge_score: Optional[int] = None,
) -> dict[str, Any]:
    """Log a manual trade against an inefficiency idea."""
    now = datetime.now(timezone.utc)
    closed = result in ("win", "loss", "be")
    meta = {
        "setup": setup,
        "result_r": result_r,
        "notes": notes,
        "inefficiency_type": inefficiency_type,
        "edge_score": edge_score,
    }
    row = {
        "user_id": SYSTEM_USER_ID,
        "symbol": symbol.upper(),
        "exchange": exchange,
        "side": direction,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "quantity": None,
        "pnl": result_r,
        "result": result or ("open" if not closed else result),
        "signal_id": signal_id,
        "opened_at": now,
        "closed_at": now if closed else None,
        "meta": meta,
    }

    if pg_up():
        try:
            async with SessionLocal() as db:
                t = Trade(**row)
                db.add(t)
                await db.commit()
                await db.refresh(t)
                return _trade_out(t)
        except Exception as exc:  # noqa: BLE001
            logger.warning("journal DB write failed, memory: %s", exc)

    row["id"] = _next_id()
    row["created_at"] = now.isoformat()
    _MEM.insert(0, row)
    return dict(row)


async def list_trades(*, limit: int = 50, setup: Optional[str] = None) -> list[dict[str, Any]]:
    if pg_up():
        try:
            async with SessionLocal() as db:
                q = select(Trade).order_by(desc(Trade.id)).limit(limit)
                rows = (await db.execute(q)).scalars().all()
                out = [_trade_out(r) for r in rows]
                if setup:
                    out = [r for r in out if (r.get("meta") or {}).get("setup") == setup]
                return out
        except Exception as exc:  # noqa: BLE001
            logger.warning("journal list DB fail: %s", exc)

    rows = list(_MEM)[:limit]
    if setup:
        rows = [r for r in rows if (r.get("meta") or {}).get("setup") == setup]
    return rows


async def journal_stats(*, setup: str = "inefficiency", min_closed: int = 1) -> dict[str, Any]:
    """WinRate from closed journal trades for Edge scoring."""
    rows = await list_trades(limit=500, setup=setup)
    closed = [r for r in rows if str(r.get("result") or "") in ("win", "loss", "be")]
    wins = [r for r in closed if r.get("result") == "win"]
    losses = [r for r in closed if r.get("result") == "loss"]
    be = [r for r in closed if r.get("result") == "be"]
    wr = (len(wins) / len(closed) * 100.0) if closed else None
    avg_r = None
    rs = [float(r["pnl"]) for r in closed if r.get("pnl") is not None]
    if rs:
        avg_r = sum(rs) / len(rs)

    by_type: dict[str, dict[str, Any]] = {}
    for r in closed:
        kind = (r.get("meta") or {}).get("inefficiency_type") or "unknown"
        bucket = by_type.setdefault(kind, {"wins": 0, "losses": 0, "be": 0, "n": 0})
        bucket["n"] += 1
        if r.get("result") == "win":
            bucket["wins"] += 1
        elif r.get("result") == "loss":
            bucket["losses"] += 1
        else:
            bucket["be"] += 1
    for v in by_type.values():
        n = max(1, v["wins"] + v["losses"])  # BE excluded from WR
        v["winrate"] = round(v["wins"] / n * 100, 1) if (v["wins"] + v["losses"]) else None

    return {
        "setup": setup,
        "closed": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(be),
        "open": len([r for r in rows if r.get("result") == "open"]),
        "winrate": round(wr, 1) if wr is not None else None,
        "avg_r": round(avg_r, 2) if avg_r is not None else None,
        "enough_sample": len(closed) >= max(min_closed, 5),
        "by_type": by_type,
        "usable_for_edge": wr is not None and len(closed) >= 5,
    }


def _trade_out(t: Trade | dict[str, Any]) -> dict[str, Any]:
    if isinstance(t, dict):
        return t
    return {
        "id": t.id,
        "user_id": t.user_id,
        "symbol": t.symbol,
        "exchange": t.exchange,
        "side": t.side,
        "entry_price": t.entry_price,
        "exit_price": t.exit_price,
        "quantity": t.quantity,
        "pnl": t.pnl,
        "result": t.result,
        "signal_id": t.signal_id,
        "opened_at": t.opened_at.isoformat() if t.opened_at else None,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        "meta": t.meta or {},
    }
