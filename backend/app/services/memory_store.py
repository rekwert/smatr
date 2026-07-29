"""In-memory signal store — fallback when PostgreSQL/Docker is unavailable."""

from __future__ import annotations

import itertools
import threading
from datetime import datetime, timezone
from typing import Any, Optional

_lock = threading.Lock()
_id_seq = itertools.count(1)
_signals: list[dict[str, Any]] = []


def clear() -> None:
    with _lock:
        _signals.clear()


def _ex_key(row: dict[str, Any]) -> str:
    return str(row.get("exchange") or "bybit").lower()


def find_active(
    symbol: str,
    timeframe: Optional[str] = None,
    exchange: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    with _lock:
        for s in _signals:
            if s.get("symbol") != symbol or s.get("status") != "active":
                continue
            if timeframe is not None and s.get("timeframe") != timeframe:
                continue
            if exchange is not None and _ex_key(s) != str(exchange).lower():
                continue
            return dict(s)
    return None


def upsert_signal(row: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        sym = row.get("symbol")
        tf = row.get("timeframe")
        ex = _ex_key(row)
        row["exchange"] = ex
        prev = None
        for s in _signals:
            if (
                s.get("symbol") == sym
                and s.get("timeframe") == tf
                and _ex_key(s) == ex
                and s.get("status") == "active"
            ):
                prev = s
                break

        if prev:
            row.setdefault("id", prev.get("id"))
            row.setdefault("created_at", prev.get("created_at"))
            from app.engines.scoring.readiness import diff_score_history, merge_replay

            row["score_history"] = diff_score_history(prev, row)
            status = str(row.get("lifecycle_status") or prev.get("lifecycle_status") or "WATCH")
            row["replay"] = merge_replay(prev, status=status)  # type: ignore[arg-type]
        elif not row.get("replay") and row.get("lifecycle_status"):
            from app.engines.scoring.readiness import build_replay_seed

            row["replay"] = build_replay_seed(str(row["lifecycle_status"]))  # type: ignore[arg-type]

        _signals[:] = [
            s
            for s in _signals
            if not (
                s.get("symbol") == sym
                and s.get("timeframe") == tf
                and _ex_key(s) == ex
                and s.get("status") == "active"
            )
        ]
        if "id" not in row:
            row["id"] = next(_id_seq)
        if "created_at" not in row:
            row["created_at"] = datetime.now(timezone.utc).isoformat()
        row.setdefault("status", "active")
        _signals.append(row)
        return row


def list_signals(
    *,
    min_score: int = 0,
    signal_type: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    with _lock:
        rows = [s for s in _signals if s.get("status") == "active" and int(s.get("score") or 0) >= min_score]
        if signal_type:
            rows = [s for s in rows if s.get("signal_type") == signal_type]
        rows.sort(key=lambda s: int(s.get("score") or 0), reverse=True)
        return rows[:limit]


def get_signal(signal_id: int) -> Optional[dict[str, Any]]:
    with _lock:
        for s in _signals:
            if int(s.get("id") or 0) == signal_id:
                return s
    return None


def counts() -> tuple[int, int]:
    with _lock:
        active = len([s for s in _signals if s.get("status") == "active"])
        spikes = len([s for s in _signals if s.get("status") == "active" and int(s.get("score") or 0) >= 85])
        return active, spikes
