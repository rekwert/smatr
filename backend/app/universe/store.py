"""In-process snapshot store for Universe Engine v2."""

from __future__ import annotations

import threading
import time
from typing import Any, Optional

_lock = threading.Lock()
_snapshot: dict[str, Any] = {
    "updated_at": None,
    "stats": {},
    "cheap": [],
    "heavy": [],
    "cross": [],
    "trade_ideas": [],
}


def save_snapshot(
    *,
    stats: dict,
    cheap: list[dict],
    heavy: list[dict],
    cross: list[dict],
    trade_ideas: list[dict],
) -> None:
    with _lock:
        _snapshot.clear()
        _snapshot.update(
            {
                "updated_at": time.time(),
                "stats": stats,
                "cheap": cheap,
                "heavy": heavy,
                "cross": cross,
                "trade_ideas": trade_ideas,
            }
        )


def get_snapshot() -> dict[str, Any]:
    with _lock:
        return dict(_snapshot)
