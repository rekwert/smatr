"""Inefficiency-first feed policy — Sweep + FVG + OB, Edge ranking, majors harder."""

from __future__ import annotations

from typing import Any, Optional

# Liquid majors: allowed only with unusually strong Edge
MAJOR_SYMBOLS = {
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "DOTUSDT",
    "LINKUSDT",
    "LTCUSDT",
    "BCHUSDT",
    "TRXUSDT",
    "TONUSDT",
    "SUIUSDT",
}

FEED_INEFFICIENCY = "inefficiency"
FEED_VOLUME_SCAN = "volume_scan"
FEED_ALL = "all"

# Default product thresholds
MIN_EDGE = 70
MIN_EDGE_MAJOR = 85
MIN_SETUP = 55
MIN_EXECUTION = 30  # soft floor — Edge primary, but reject dead execution


def is_major(symbol: str) -> bool:
    return str(symbol or "").upper() in MAJOR_SYMBOLS


def _comp(components: dict[str, Any], key: str) -> float:
    try:
        return float(components.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def structure_confirmed(
    *,
    checklist: Optional[dict[str, Any]] = None,
    components: Optional[dict[str, Any]] = None,
) -> bool:
    """Hard thesis: Liquidity Sweep + FVG + Order Block."""
    cl = checklist or {}
    co = components or {}
    sweep = bool(cl.get("liquidity_sweep")) or _comp(co, "liquidity_sweep") >= 55
    fvg = bool(cl.get("fvg")) or _comp(co, "fvg") >= 50
    ob = bool(cl.get("order_block")) or _comp(co, "order_block") >= 50
    # Equivalent structural confirmation: both imbalance + block present
    return sweep and fvg and ob


def edge_threshold(symbol: str) -> int:
    return MIN_EDGE_MAJOR if is_major(symbol) else MIN_EDGE


def _pick_int(row: dict[str, Any], *keys: str, default: int = 0) -> int:
    reason = row.get("reason") if isinstance(row.get("reason"), dict) else {}
    for k in keys:
        if row.get(k) is not None:
            try:
                return int(row.get(k) or 0)
            except (TypeError, ValueError):
                pass
        if isinstance(reason, dict) and reason.get(k) is not None:
            try:
                return int(reason.get(k) or 0)
            except (TypeError, ValueError):
                pass
    return default


def extract_structure(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    reason = row.get("reason") if isinstance(row.get("reason"), dict) else {}
    checklist = reason.get("checklist") if isinstance(reason.get("checklist"), dict) else {}
    if not checklist and isinstance(row.get("checklist"), dict):
        checklist = row["checklist"]
    components = reason.get("components") if isinstance(reason.get("components"), dict) else {}
    if not components and isinstance(row.get("components"), dict):
        components = row["components"]
    return checklist, components


def feed_of(row: dict[str, Any]) -> str:
    reason = row.get("reason") if isinstance(row.get("reason"), dict) else {}
    return str(row.get("feed") or reason.get("feed") or FEED_VOLUME_SCAN)


def inefficiency_event_ok(row: dict[str, Any]) -> bool:
    """Accept flash OR classic Sweep+FVG+OB with real displacement."""
    reason = row.get("reason") if isinstance(row.get("reason"), dict) else {}
    if row.get("inefficiency_qualifies") is True or reason.get("inefficiency_qualifies") is True:
        return True
    kind = row.get("inefficiency_type") or reason.get("inefficiency_type")
    if kind == "flash_spike":
        return True
    checklist, components = extract_structure(row)
    if not structure_confirmed(checklist=checklist, components=components):
        return False
    # Require measurable displacement so feed is not SMC noise
    disp = 0.0
    for src in (row, reason, components):
        if isinstance(src, dict) and src.get("displacement_pct") is not None:
            try:
                disp = float(src.get("displacement_pct") or 0)
                break
            except (TypeError, ValueError):
                pass
    impulse = _comp(components, "impulse_pct")
    return max(disp, impulse) >= 2.0 or _comp(components, "liquidity_sweep") >= 70


def qualifies_inefficiency(row: dict[str, Any]) -> bool:
    """Main product gate for dashboard / default signals list."""
    if feed_of(row) == FEED_VOLUME_SCAN:
        return False
    symbol = str(row.get("symbol") or "")
    if not inefficiency_event_ok(row):
        return False
    setup = _pick_int(row, "setup_score", "score", default=0)
    execution = _pick_int(row, "execution_score", default=0)
    edge = _pick_int(row, "edge_score", default=0)
    if setup < MIN_SETUP:
        return False
    if execution < MIN_EXECUTION:
        return False
    if edge < edge_threshold(symbol):
        return False
    return True


def reason_universe(row: dict[str, Any]) -> bool:
    reason = row.get("reason") if isinstance(row.get("reason"), dict) else {}
    return bool(reason.get("universe_v2") or row.get("universe_v2"))


def sort_key_inefficiency(row: dict[str, Any]) -> tuple[int, int, int]:
    """Sort: Edge desc, Execution desc, Setup desc."""
    edge = _pick_int(row, "edge_score", default=0)
    execution = _pick_int(row, "execution_score", default=0)
    setup = _pick_int(row, "setup_score", "score", default=0)
    return (edge, execution, setup)


def filter_and_sort(
    rows: list[dict[str, Any]],
    *,
    feed: str = FEED_INEFFICIENCY,
    min_score: int = 0,
    limit: int = 50,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows:
        score = _pick_int(r, "score", "setup_score", default=0)
        if score < min_score:
            continue
        if feed == FEED_INEFFICIENCY:
            if not qualifies_inefficiency(r):
                continue
        elif feed == FEED_VOLUME_SCAN:
            if feed_of(r) != FEED_VOLUME_SCAN:
                continue
        out.append(r)
    out.sort(key=sort_key_inefficiency, reverse=True)
    return out[:limit]


def annotate_feed(analysis_or_row: dict[str, Any], feed: str) -> dict[str, Any]:
    """Stamp feed on payload / reason for persistence."""
    analysis_or_row["feed"] = feed
    reason = analysis_or_row.get("reason")
    if isinstance(reason, dict):
        reason = dict(reason)
        reason["feed"] = feed
        analysis_or_row["reason"] = reason
    return analysis_or_row


def should_persist_inefficiency(analysis: dict[str, Any]) -> tuple[bool, str]:
    """Gate before writing to main inefficiency memory/DB."""
    if analysis.get("inefficiency_qualifies") is True:
        setup = int(analysis.get("setup_score") or analysis.get("score") or 0)
        execution = int(analysis.get("execution_score") or 0)
        edge = int(analysis.get("edge_score") or 0)
        symbol = str(analysis.get("symbol") or "")
        if setup < MIN_SETUP:
            return False, f"setup<{MIN_SETUP}"
        if execution < MIN_EXECUTION:
            return False, f"exec<{MIN_EXECUTION}"
        need = edge_threshold(symbol)
        if edge < need:
            return False, f"edge<{need}"
        return True, "ok"

    checklist = (analysis.get("reasons") or {}).get("checklist") or analysis.get("checklist") or {}
    components = analysis.get("components") or {}
    if not structure_confirmed(checklist=checklist, components=components):
        return False, "need Sweep+FVG+OB or flash"
    disp = float(analysis.get("displacement_pct") or components.get("impulse_pct") or 0)
    if disp < 2.0 and float(components.get("liquidity_sweep") or 0) < 70:
        return False, "weak displacement"
    setup = int(analysis.get("setup_score") or analysis.get("score") or 0)
    execution = int(analysis.get("execution_score") or 0)
    edge = int(analysis.get("edge_score") or 0)
    symbol = str(analysis.get("symbol") or "")
    if setup < MIN_SETUP:
        return False, f"setup<{MIN_SETUP}"
    if execution < MIN_EXECUTION:
        return False, f"exec<{MIN_EXECUTION}"
    need = edge_threshold(symbol)
    if edge < need:
        return False, f"edge<{need}"
    return True, "ok"
