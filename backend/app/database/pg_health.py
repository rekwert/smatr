"""Postgres availability helper — works on local :5433 and Docker hostname."""

from __future__ import annotations

import logging
import socket
from urllib.parse import urlparse

from app.config.settings import settings

logger = logging.getLogger(__name__)
_cached: bool | None = None


def _hosts_to_probe() -> list[tuple[str, int]]:
    hosts: list[tuple[str, int]] = [("127.0.0.1", 5433), ("127.0.0.1", 5432)]
    raw = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    try:
        u = urlparse(raw)
        if u.hostname:
            port = u.port or 5432
            hosts.insert(0, (u.hostname, port))
    except Exception:  # noqa: BLE001
        pass
    # de-dupe
    seen: set[tuple[str, int]] = set()
    out: list[tuple[str, int]] = []
    for h in hosts:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def pg_up(timeout: float = 0.5) -> bool:
    global _cached
    for host, port in _hosts_to_probe():
        try:
            with socket.create_connection((host, port), timeout=timeout):
                _cached = True
                return True
        except OSError:
            continue
    _cached = False
    return False
